"""
LLM Orchestration Service — LegalLens
Implements: architecture.md §6.4 LLM Orchestration Module.
Responsibility: Construct grounded prompts, call Claude API, parse/validate citations.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


class Citation(BaseModel):
    """Citation linking a claim to a source chunk."""
    chunk_id: uuid.UUID
    page_number: int | None
    excerpt: str


class GroundedResponse(BaseModel):
    """LLM response with validated citations."""
    model_config = {"protected_namespaces": ()}
    
    task: Literal["simplify", "chat", "extract_clauses", "compare"]
    content: str
    citations: list[Citation]
    model_used: str


# ── Model Configuration ───────────────────────────────────────────────────────


# architecture.md §4: model IDs for Claude API
MODEL_SONNET = "claude-sonnet-4-20250514"  # Generation tasks (simplify, chat, compare)
MODEL_HAIKU = "claude-haiku-4-5-20251001"  # Classification tasks (clause extraction)

# Token limits per architecture.md §6.4
MAX_TOKENS_GENERATION = 8192
MAX_TOKENS_CLASSIFICATION = 4096


# ── Prompt Template Loading ───────────────────────────────────────────────────


def _load_prompt_template(task: str) -> str:
    """
    Load versioned prompt template for the given task.
    
    Templates stored in app/prompts/ per architecture.md §5 directory structure.
    """
    template_map = {
        "simplify": "simplify.md",
        "extract_clauses": "extract_clauses.md",
        "chat": "chat.md",
        "compare": "compare.md",
    }
    
    template_file = template_map.get(task)
    if not template_file:
        raise ValueError(f"No prompt template for task: {task}")
    
    template_path = Path(__file__).parent.parent / "prompts" / template_file
    
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Citation Parsing ──────────────────────────────────────────────────────────


def parse_citations_from_text(text: str) -> list[str]:
    """
    Extract chunk IDs from [chunk:uuid] citations in text.
    
    Returns list of unique chunk ID strings. Validates UUID format.
    """
    # Match [chunk:uuid] format with or without hyphens
    pattern = r'\[chunk:([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})\]'
    matches = re.findall(pattern, text)
    
    # Also try to extract from JSON citations array if present
    try:
        # Look for "citations": [...] in JSON
        json_pattern = r'"citations"\s*:\s*\[([^\]]+)\]'
        json_match = re.search(json_pattern, text)
        if json_match:
            citations_json = json_match.group(1)
            # Extract chunk_id values
            chunk_id_pattern = r'"chunk_id"\s*:\s*"([a-fA-F0-9-]+)"'
            json_matches = re.findall(chunk_id_pattern, citations_json)
            matches.extend(json_matches)
    except Exception:
        pass  # JSON parsing is best-effort
    
    # Normalize UUIDs (add hyphens if missing) and deduplicate
    normalized = []
    seen = set()
    
    for match in matches:
        try:
            # Parse and re-stringify to normalize format
            chunk_uuid = uuid.UUID(match)
            chunk_str = str(chunk_uuid)
            if chunk_str not in seen:
                normalized.append(chunk_str)
                seen.add(chunk_str)
        except ValueError:
            # Invalid UUID, skip
            logger.warning(f"Invalid UUID in citation: {match}")
            continue
    
    return normalized


def _validate_citations(
    text: str,
    context_chunks: list[DocumentChunk],
) -> list[Citation]:
    """
    Extract and validate citations against provided chunks.
    
    Returns only citations that reference chunks in context_chunks.
    """
    chunk_map = {str(chunk.id): chunk for chunk in context_chunks}
    citation_ids = parse_citations_from_text(text)
    
    validated_citations = []
    
    for chunk_id_str in citation_ids:
        chunk = chunk_map.get(chunk_id_str)
        if chunk:
            # Create Citation object with chunk metadata
            citation = Citation(
                chunk_id=uuid.UUID(chunk_id_str),
                page_number=chunk.page_number,
                excerpt=chunk.text[:200],  # First 200 chars as excerpt
            )
            validated_citations.append(citation)
        else:
            # Invalid citation - chunk not in context
            logger.warning(
                f"Citation references chunk not in context: {chunk_id_str}"
            )
    
    return validated_citations


# ── Prompt Construction ───────────────────────────────────────────────────────


def _build_system_prompt(task: str) -> str:
    """
    Build system prompt with legal disclaimer and task template.
    
    Per architecture.md §3 step 6: Must include "informational, not legal advice".
    """
    template = _load_prompt_template(task)
    
    # Common system directive for all tasks
    base_directive = (
        "You are a legal document assistant for LegalLens.\n\n"
        "CRITICAL: This is an informational tool, not legal advice. "
        "All outputs are for informational purposes only and do not constitute "
        "legal advice. Users should consult a qualified attorney for legal guidance.\n\n"
    )
    
    return base_directive + template


def _build_user_message(
    task: str,
    context_chunks: list[DocumentChunk],
    user_input: str,
    reading_level: str | None = None,
    history: str | None = None,
) -> str:
    """
    Build user message with context chunks and task-specific input.
    
    Includes chunk IDs for citation tracking.
    For chat tasks, includes conversation history if provided.
    """
    # Build context section with all chunks
    context_parts = ["# Source Document Chunks\n"]
    
    for chunk in context_chunks:
        context_parts.append(
            f"\n## [Chunk ID: {chunk.id}]\n"
            f"Page: {chunk.page_number or 'N/A'}\n"
            f"Chunk Index: {chunk.chunk_index}\n"
            f"Content:\n{chunk.text}\n"
        )
    
    context_text = "\n".join(context_parts)
    
    # Build task-specific request
    if task == "simplify":
        if not reading_level:
            reading_level = "plain_english"
        request = (
            f"\n\n# Task\n\n"
            f"Simplify the above document text to the **{reading_level}** reading level.\n\n"
            f"Follow the instructions in the system prompt. Return your response as JSON "
            f"with the structure specified in the prompt template.\n\n"
            f"Remember to cite sources using [chunk:UUID] format inline."
        )
    elif task == "chat":
        # Include conversation history if provided
        history_section = ""
        if history:
            history_section = (
                f"\n\n# Conversation History\n\n"
                f"{history}\n"
            )
        
        request = (
            f"{history_section}"
            f"\n\n# User Question\n\n"
            f"{user_input}\n\n"
            f"Answer the question based ONLY on the provided document chunks. "
            f"Cite your sources using [chunk:UUID] format after each factual claim. "
            f"If the answer is not in the provided text, say so explicitly."
        )
    elif task == "extract_clauses":
        # user_input contains the clause type to extract
        request = (
            f"\n\n# Task\n\n"
            f"Extract all **{user_input}** clauses from the above chunks.\n\n"
            f"Return a JSON array of identified clauses following the schema "
            f"in the system prompt. Include start_offset, end_offset, risk_level, "
            f"and risk_rationale for each clause.\n\n"
            f"If no clauses of this type are found, return an empty array: []"
        )
    elif task == "compare":
        request = (
            f"\n\n# Task\n\n"
            f"Compare the clauses across the provided document chunks and identify "
            f"material differences.\n\n"
            f"{user_input}\n\n"
            f"Follow the comparison template in the system prompt."
        )
    else:
        raise ValueError(f"Unknown task: {task}")
    
    return context_text + request


# ── Main API Function ─────────────────────────────────────────────────────────


async def generate_grounded_response(
    task: Literal["simplify", "chat", "extract_clauses", "compare"],
    context_chunks: list[DocumentChunk],
    user_input: str,
    reading_level: str | None = None,
    history: str | None = None,
) -> GroundedResponse:
    """
    Generate a grounded LLM response with validated citations.
    
    Per architecture.md §6.4:
    - Constructs prompt with retrieved context + citation requirement
    - Calls Claude API (model selection based on task)
    - Parses and validates citations
    - Returns structured response
    
    Args:
        task: Type of generation task
        context_chunks: Document chunks to ground the response
        user_input: User's query/request (empty for simplify)
        reading_level: For simplify task only (elementary/plain_english/detailed)
        history: For chat task only - conversation history (formatted string)
    
    Returns:
        GroundedResponse with content and validated citations
    
    Raises:
        ValueError: Invalid inputs or LLM API failure
    """
    # Validation
    if not context_chunks:
        raise ValueError("At least one context chunk required")
    
    if task == "simplify":
        valid_levels = {"elementary", "plain_english", "detailed"}
        if reading_level and reading_level not in valid_levels:
            raise ValueError(
                f"reading_level must be one of {valid_levels} for simplify task, "
                f"got: {reading_level}"
            )
    
    # Select model based on task
    # Per architecture.md §4: haiku for classification, sonnet for generation
    if task == "extract_clauses":
        model = MODEL_HAIKU
        max_tokens = MAX_TOKENS_CLASSIFICATION
    else:
        model = MODEL_SONNET
        max_tokens = MAX_TOKENS_GENERATION
    
    # Build prompt
    system_prompt = _build_system_prompt(task)
    user_message = _build_user_message(
        task, context_chunks, user_input, reading_level, history
    )
    
    # Call Claude API
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    try:
        logger.info(
            f"Calling Claude API: task={task}, model={model}, "
            f"chunks={len(context_chunks)}, tokens={max_tokens}"
        )
        
        message = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            temperature=0.3,  # Lower temp for factual/legal content
        )
        
        # Extract text content
        if not message.content or len(message.content) == 0:
            raise ValueError("Empty response from Claude API")
        
        response_text = message.content[0].text
        
        logger.info(
            f"Claude API response: stop_reason={message.stop_reason}, "
            f"length={len(response_text)}"
        )
        
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise ValueError(f"LLM generation failed: {e}") from e
    
    # Parse response based on task
    if task in ("simplify", "extract_clauses"):
        # Expecting JSON response
        try:
            # Try to extract JSON if wrapped in markdown code blocks
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                json_text = response_text
            
            # For simplify, we get an object; for extract_clauses, an array
            parsed = json.loads(json_text)
            
            if task == "simplify":
                content = parsed.get("simplified_text", response_text)
            else:
                # extract_clauses returns array - convert to text for now
                content = json.dumps(parsed, indent=2)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(
                f"Failed to parse LLM response as JSON: {e}. "
                f"Response was: {response_text[:200]}"
            ) from e
    else:
        # chat/compare: plain text response
        content = response_text
    
    # Validate citations
    citations = _validate_citations(response_text, context_chunks)
    
    logger.info(
        f"Response generated: task={task}, citations={len(citations)}, "
        f"content_length={len(content)}"
    )
    
    return GroundedResponse(
        task=task,
        content=content,
        citations=citations,
        model_used=model,
    )
