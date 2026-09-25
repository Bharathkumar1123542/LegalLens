"""
Chat API endpoints — LegalLens Phase 4
Implements: architecture.md §8 chat endpoints for document Q&A.
Routes: POST /documents/{id}/chat/sessions, POST /chat/sessions/{id}/messages,
        GET /chat/sessions/{id}/messages, GET /documents/{id}/chat/sessions
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbDep
from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.schemas.chat import (
    StartChatRequest,
    ChatSessionCreatedResponse,
    ChatSessionResponse,
    AskQuestionRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
    ChatSessionListResponse,
)
from app.services import chat as chat_service
from app.services.audit import record_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# Also need document-scoped router for session creation
documents_router = APIRouter(tags=["chat"])


# ── Helper functions ──────────────────────────────────────────────────────────

async def _get_owned_session(
    session_id: uuid.UUID,
    current_user,
    db: AsyncSession,
) -> ChatSession:
    """
    Get a chat session and verify ownership.
    
    Raises:
        HTTPException: 404 if not found, 403 if not owned by current user
    """
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session {session_id} not found",
        )
    
    if session.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this chat session",
        )
    
    return session


async def _get_owned_document(
    document_id: uuid.UUID,
    current_user,
    db: AsyncSession,
) -> Document:
    """
    Get a document and verify ownership.
    
    Raises:
        HTTPException: 404 if not found, 403 if not owned
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    
    if doc.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document",
        )
    
    return doc


# ── Endpoints ─────────────────────────────────────────────────────────────────

@documents_router.post(
    "/documents/{document_id}/chat/sessions",
    response_model=ChatSessionCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new chat session for a document",
    responses={
        404: {"description": "Document not found"},
        403: {"description": "Not authorized to access document"},
        409: {"description": "Document not ready (still processing)"},
    },
)
async def create_chat_session(
    document_id: uuid.UUID,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> ChatSessionCreatedResponse:
    """
    Create a new chat session for a document.
    
    Per architecture.md §5.7:
    - Verify document exists, is ready, and owned by user
    - Create ChatSession record
    
    Client can then use POST /chat/sessions/{id}/messages to ask questions.
    """
    # Verify document ownership and readiness
    await _get_owned_document(document_id, current_user, db)
    
    # Audit the session creation
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="chat.session_created",
        resource_type="document",
        resource_id=document_id,
        metadata={},
        ip_address=ip,
    )
    
    try:
        # Create session via service
        session = await chat_service.start_chat_session(
            db=db,
            document_id=document_id,
            owner_id=current_user.id,
        )
        
        logger.info(
            f"chat.session_created: session={session.id}, "
            f"document={document_id}, user={current_user.id}"
        )
        
        return ChatSessionCreatedResponse(
            session=ChatSessionResponse.model_validate(session),
        )
        
    except ValueError as e:
        # Document not ready or other validation error
        logger.error(
            f"chat.session_creation_failed: document={document_id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    
    except Exception as e:
        logger.error(
            f"chat.session_creation_unexpected_error: "
            f"document={document_id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session",
        ) from e


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question in a chat session",
    responses={
        404: {"description": "Chat session not found"},
        403: {"description": "Not authorized to access session"},
        502: {"description": "LLM generation failed"},
    },
)
async def ask_question_endpoint(
    session_id: uuid.UUID,
    request_body: AskQuestionRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> ChatMessageResponse:
    """
    Ask a question in a chat session.
    
    Per architecture.md §5.7:
    - Retrieve relevant chunks via RAG (semantic search)
    - Load conversation history
    - Generate grounded answer with citations
    - Persist user question and assistant answer
    
    Per architecture.md §7.2:
    - Assistant messages MUST include citations (non-empty) when making factual claims
    """
    # Verify session ownership
    session = await _get_owned_session(session_id, current_user, db)
    
    # Audit the question
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="chat.question_asked",
        resource_type="chat_session",
        resource_id=session_id,
        metadata={"question_length": len(request_body.question)},
        ip_address=ip,
    )
    
    try:
        # Ask question via service (includes RAG retrieval + LLM generation)
        logger.info(
            f"chat.question: session={session_id}, "
            f"question_len={len(request_body.question)}, "
            f"top_k={request_body.top_k}"
        )
        
        message = await chat_service.ask_question(
            db=db,
            session_id=session_id,
            document_id=session.document_id,
            question=request_body.question,
            top_k=request_body.top_k,
        )
        
        logger.info(
            f"chat.answer_generated: session={session_id}, "
            f"message={message.id}, citations={len(message.citations)}"
        )
        
        # Convert to response schema with citations
        return ChatMessageResponse.from_orm_with_citations(message)
        
    except ValueError as e:
        # No relevant chunks, session not found, or generation failed
        logger.error(
            f"chat.question_failed: session={session_id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate answer: {str(e)}",
        ) from e
    
    except Exception as e:
        logger.error(
            f"chat.unexpected_error: session={session_id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve chat history for a session",
    responses={
        404: {"description": "Chat session not found"},
        403: {"description": "Not authorized to access session"},
    },
)
async def get_chat_history_endpoint(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
    limit: int | None = None,
    offset: int = 0,
) -> ChatHistoryResponse:
    """
    Retrieve chat message history for a session.
    
    Returns all messages (user and assistant) ordered by created_at (oldest first).
    Optional pagination via limit/offset parameters.
    """
    # Verify session ownership
    await _get_owned_session(session_id, current_user, db)
    
    # Get history via service
    messages = await chat_service.get_chat_history(
        db=db,
        session_id=session_id,
        limit=limit,
        offset=offset,
    )
    
    # Count total messages
    count_result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    total = len(count_result.scalars().all())
    
    logger.info(
        f"chat.history_retrieved: session={session_id}, "
        f"returned={len(messages)}, total={total}"
    )
    
    # Convert to response schema
    message_responses = [
        ChatMessageResponse.from_orm_with_citations(msg)
        for msg in messages
    ]
    
    return ChatHistoryResponse(
        session_id=session_id,
        messages=message_responses,
        total=total,
        page=offset // limit + 1 if limit else None,
        page_size=limit,
    )


@documents_router.get(
    "/documents/{document_id}/chat/sessions",
    response_model=ChatSessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all chat sessions for a document",
    responses={
        404: {"description": "Document not found"},
        403: {"description": "Not authorized to access document"},
    },
)
async def list_chat_sessions_endpoint(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> ChatSessionListResponse:
    """
    List all chat sessions for a document.
    
    Returns sessions ordered by last_message_at desc (most recent first).
    """
    # Verify document ownership
    await _get_owned_document(document_id, current_user, db)
    
    # Get sessions via service
    sessions = await chat_service.list_chat_sessions(
        db=db,
        document_id=document_id,
        owner_id=current_user.id,
    )
    
    logger.info(
        f"chat.sessions_listed: document={document_id}, "
        f"count={len(sessions)}"
    )
    
    # Convert to response schema
    session_responses = [
        ChatSessionResponse.model_validate(session)
        for session in sessions
    ]
    
    return ChatSessionListResponse(
        document_id=document_id,
        sessions=session_responses,
        total=len(sessions),
    )
