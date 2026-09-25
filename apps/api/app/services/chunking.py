"""
Text Chunking Service — LegalLens Phase 2
Implements: architecture.md §7.2 chunking rules.
  - Target: 500 tokens per chunk
  - Hard cap: 700 tokens
  - Overlap: 50 tokens between consecutive chunks
  - Split at sentence boundaries when possible
"""

from __future__ import annotations

import re
from typing import TypedDict

import structlog
import tiktoken

log = structlog.get_logger(__name__)

# Token counting: use cl100k_base encoding (GPT-4/Claude tokenizer approximation)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Chunking parameters (architecture.md §7.2)
TARGET_TOKENS = 500
MAX_TOKENS = 700
OVERLAP_TOKENS = 50


class ChunkDict(TypedDict):
    """Single chunk metadata."""
    chunk_index: int
    page_number: int | None
    text: str
    token_count: int


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.
    Returns 0 for empty/whitespace-only text.
    """
    if not text or not text.strip():
        return 0
    return len(_TOKENIZER.encode(text))


def split_at_sentence_boundary(text: str, target_pos: int) -> str:
    """
    Find the nearest sentence boundary before target_pos.
    Sentence boundaries: . ! ? followed by whitespace or end-of-string.
    Ignores common abbreviations (Dr., Inc., etc.).
    
    If no boundary found within reasonable range, performs hard cut at target_pos.
    """
    # Common abbreviations that shouldn't be treated as sentence endings
    abbreviations = r"\b(?:Dr|Mr|Mrs|Ms|Prof|Inc|Ltd|Corp|etc|vs|e\.g|i\.e)\."
    
    # Search backwards from target_pos for sentence boundary
    search_range = text[:target_pos]
    
    # Find all sentence-ending punctuation
    pattern = r"[.!?](?=\s|$)"
    matches = list(re.finditer(pattern, search_range))
    
    if not matches:
        # No sentence boundary found — hard cut
        return text[:target_pos]
    
    # Take the last match, but verify it's not an abbreviation
    for match in reversed(matches):
        end_pos = match.end()
        # Check if this period is part of an abbreviation
        preceding = text[max(0, end_pos - 20):end_pos]
        if not re.search(abbreviations, preceding, re.IGNORECASE):
            return text[:end_pos]
    
    # All matches were abbreviations — hard cut
    return text[:target_pos]


def chunk_text(text: str, page_number: int | None) -> list[ChunkDict]:
    """
    Chunk text into TARGET_TOKENS-sized chunks with OVERLAP_TOKENS overlap.
    Splits at sentence boundaries when possible.
    
    Args:
        text: Full document text
        page_number: Page number (for PDFs) or None (for DOCX/TXT)
    
    Returns:
        List of chunks with metadata
    """
    text = text.strip()
    if not text:
        return []
    
    chunks: list[ChunkDict] = []
    chunk_index = 0
    start = 0
    
    while start < len(text):
        # Calculate target end position
        # Estimate: ~1.3 tokens per word, ~5 chars per word → ~6.5 chars per token
        target_chars = TARGET_TOKENS * 6
        max_chars = MAX_TOKENS * 6
        
        end = start + target_chars
        
        # If remaining text is small, take it all
        if end >= len(text):
            chunk_text_str = text[start:]
        else:
            # Try to split at sentence boundary
            chunk_text_str = split_at_sentence_boundary(text[start:end + 200], target_chars)
            # If chunk_text_str is still longer than max, enforce hard cap
            if count_tokens(chunk_text_str) > MAX_TOKENS:
                # Binary search for the exact character position that gives MAX_TOKENS
                chunk_text_str = _truncate_to_token_limit(text[start:], MAX_TOKENS)
        
        token_count = count_tokens(chunk_text_str)
        
        if token_count > 0:
            chunks.append({
                "chunk_index": chunk_index,
                "page_number": page_number,
                "text": chunk_text_str,
                "token_count": token_count,
            })
            chunk_index += 1
        
        # Calculate next start position with overlap
        overlap_chars = OVERLAP_TOKENS * 6
        start += len(chunk_text_str) - overlap_chars
        
        # Ensure we make progress (avoid infinite loop if chunk is tiny)
        if start <= chunks[-1]["text"][:10].find(text[start:start+10]):
            start += max(1, len(chunk_text_str) // 2)
    
    log.info("text.chunked", chunk_count=len(chunks), page_number=page_number)
    return chunks


def _truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """
    Binary search to find the longest substring that fits within max_tokens.
    Used when a chunk exceeds MAX_TOKENS even after sentence boundary splitting.
    """
    if count_tokens(text) <= max_tokens:
        return text
    
    left, right = 0, len(text)
    result = ""
    
    while left <= right:
        mid = (left + right) // 2
        candidate = text[:mid]
        tokens = count_tokens(candidate)
        
        if tokens <= max_tokens:
            result = candidate
            left = mid + 1
        else:
            right = mid - 1
    
    return result
