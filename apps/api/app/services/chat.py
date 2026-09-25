"""
Chat service — LegalLens Phase 4
Implements: architecture.md §5.7 Conversational Q&A Module.
Functions: start_chat_session(), ask_question() with RAG retrieval.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.services.embedding import retrieve_relevant_chunks
from app.services.llm_orchestration import generate_grounded_response

logger = logging.getLogger(__name__)


async def start_chat_session(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> ChatSession:
    """
    Start a new chat session for a document.
    
    Per architecture.md §5.7:
    - Verify document exists and is ready
    - Create ChatSession record
    
    Args:
        db: Database session
        document_id: Document to chat about
        owner_id: User creating the session
    
    Returns:
        Created ChatSession
    
    Raises:
        ValueError: If document not found or not ready
    """
    # Verify document exists and is ready
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise ValueError(f"Document {document_id} not found")
    
    if document.status != "ready":
        raise ValueError(
            f"Document {document_id} status is '{document.status}'. "
            f"Must be 'ready' to start chat."
        )
    
    # Create session
    session = ChatSession(
        document_id=document_id,
        owner_id=owner_id,
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    logger.info(
        f"chat_session.created: session={session.id}, "
        f"document={document_id}, owner={owner_id}"
    )
    
    return session


async def ask_question(
    db: AsyncSession,
    session_id: uuid.UUID,
    document_id: uuid.UUID,
    question: str,
    top_k: int = 8,
    history_limit: int = 10,
) -> ChatMessage:
    """
    Ask a question in a chat session.
    
    Per architecture.md §5.7:
    - Retrieve relevant chunks via semantic search
    - Load conversation history
    - Generate grounded response with citations
    - Persist user question and assistant answer
    - Update session.last_message_at
    
    Args:
        db: Database session
        session_id: Chat session ID
        document_id: Document ID (for retrieval)
        question: User's question
        top_k: Number of chunks to retrieve (default 8)
        history_limit: Number of previous messages to include (default 10)
    
    Returns:
        Assistant's ChatMessage with citations
    
    Raises:
        ValueError: If session not found or no relevant context
    """
    # Verify session exists
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise ValueError(f"Chat session {session_id} not found")
    
    # Retrieve relevant chunks via RAG
    logger.info(
        f"chat.retrieve: session={session_id}, question_len={len(question)}, "
        f"top_k={top_k}"
    )
    
    relevant_chunks = await retrieve_relevant_chunks(
        db=db,
        document_id=document_id,
        query=question,
        top_k=top_k,
    )
    
    if not relevant_chunks:
        raise ValueError(
            f"No relevant context found for question in document {document_id}"
        )
    
    logger.info(
        f"chat.retrieved: session={session_id}, chunks={len(relevant_chunks)}"
    )
    
    # Load conversation history (last N messages)
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(history_limit)
    )
    history_messages = history_result.scalars().all()
    
    # Reverse to chronological order (oldest first)
    history_messages = list(reversed(history_messages))
    
    # Format history for prompt
    history_text = ""
    if history_messages:
        for msg in history_messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            history_text += f"{role_label}: {msg.content}\n\n"
    
    logger.info(
        f"chat.history: session={session_id}, messages={len(history_messages)}"
    )
    
    # Generate grounded response
    try:
        grounded_response = await generate_grounded_response(
            task="chat",
            context_chunks=relevant_chunks,
            user_input=question,
            history=history_text if history_text else None,
        )
        
        logger.info(
            f"chat.generated: session={session_id}, "
            f"citations={len(grounded_response.citations)}"
        )
        
    except Exception as e:
        logger.error(f"chat.generation_failed: session={session_id}, error={e}")
        raise ValueError(f"Failed to generate answer: {e}") from e
    
    # Persist user message
    user_message = ChatMessage(
        session_id=session_id,
        role="user",
        content=question,
        citations=[],  # User messages have no citations
    )
    db.add(user_message)
    
    # Persist assistant message with citations
    citations_json = [
        {
            "chunk_id": str(citation.chunk_id),
            "page_number": citation.page_number,
            "excerpt": citation.excerpt,
        }
        for citation in grounded_response.citations
    ]
    
    assistant_message = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=grounded_response.text,
        citations=citations_json,
    )
    db.add(assistant_message)
    
    # Update session last_message_at
    session.last_message_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(assistant_message)
    
    logger.info(
        f"chat.message_saved: session={session_id}, "
        f"message={assistant_message.id}"
    )
    
    return assistant_message


async def get_chat_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    limit: int | None = None,
    offset: int = 0,
) -> list[ChatMessage]:
    """
    Retrieve chat history for a session.
    
    Args:
        db: Database session
        session_id: Chat session ID
        limit: Max number of messages to return (None = all)
        offset: Number of messages to skip (for pagination)
    
    Returns:
        List of ChatMessage ordered by created_at (oldest first)
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset(offset)
    )
    
    if limit:
        stmt = stmt.limit(limit)
    
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    return list(messages)


async def list_chat_sessions(
    db: AsyncSession,
    document_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ChatSession]:
    """
    List all chat sessions for a document.
    
    Args:
        db: Database session
        document_id: Document ID
        owner_id: User ID (for ownership verification)
    
    Returns:
        List of ChatSession ordered by last_message_at desc (most recent first)
    """
    result = await db.execute(
        select(ChatSession)
        .where(
            ChatSession.document_id == document_id,
            ChatSession.owner_id == owner_id,
        )
        .order_by(ChatSession.last_message_at.desc())
    )
    
    sessions = result.scalars().all()
    
    return list(sessions)
