"""
Unit tests — text chunking service
Tests: 500-token target chunks, 50-token overlap, sentence boundary splitting, ordering.
Covers: architecture.md §7.2 validation rules, §3 step 2 chunking.
"""

import pytest

from app.services.chunking import chunk_text, split_at_sentence_boundary, count_tokens


class TestTokenCounting:
    """Test token counting utility."""

    def test_count_tokens_simple_text(self):
        text = "This is a simple sentence with ten words in it total."
        # Rough heuristic: ~1.3 tokens per word
        tokens = count_tokens(text)
        assert 10 <= tokens <= 15

    def test_count_tokens_empty_text(self):
        assert count_tokens("") == 0
        assert count_tokens("   ") == 0

    def test_count_tokens_long_text(self):
        # 100 words
        text = " ".join(["word"] * 100)
        tokens = count_tokens(text)
        assert 80 <= tokens <= 150


class TestSentenceBoundarySplitting:
    """Test sentence boundary detection."""

    def test_split_at_sentence_boundary_finds_period(self):
        text = "First sentence. Second sentence. Third sentence."
        result = split_at_sentence_boundary(text, target_pos=20)
        
        # Should split after "First sentence."
        assert result == "First sentence."

    def test_split_at_sentence_boundary_finds_question_mark(self):
        text = "What is this? Another question? A third one?"
        result = split_at_sentence_boundary(text, target_pos=15)
        
        assert result == "What is this?"

    def test_split_at_sentence_boundary_finds_exclamation(self):
        text = "Wow! Amazing! Fantastic!"
        result = split_at_sentence_boundary(text, target_pos=10)
        
        assert result == "Wow!"

    def test_split_at_sentence_boundary_no_boundary_found(self):
        # No sentence boundary near target
        text = "This is one very long sentence without any punctuation marks"
        result = split_at_sentence_boundary(text, target_pos=30)
        
        # Should return up to target_pos (hard cut)
        assert result == text[:30]

    def test_split_at_sentence_boundary_respects_abbreviations(self):
        # Dr. and Inc. should not be treated as sentence endings
        text = "Dr. Smith works at Acme Inc. He is a doctor. She is a CEO."
        result = split_at_sentence_boundary(text, target_pos=40)
        
        # Should split after "He is a doctor." not after "Inc."
        assert "He is a doctor." in result


class TestTextChunking:
    """Test main chunking function."""

    def test_chunk_text_small_document(self):
        # Document smaller than chunk size
        text = "This is a short document. It has only two sentences."
        chunks = chunk_text(text, page_number=1)
        
        assert len(chunks) == 1
        assert chunks[0]["chunk_index"] == 0
        assert chunks[0]["page_number"] == 1
        assert chunks[0]["text"] == text
        assert chunks[0]["token_count"] < 100

    def test_chunk_text_creates_multiple_chunks(self):
        # Document large enough for multiple chunks
        # Generate ~1000 tokens worth of text
        sentence = "This is a sentence that will be repeated many times to create a large document. "
        text = sentence * 100  # ~1300 tokens
        
        chunks = chunk_text(text, page_number=1)
        
        # Should create 2-3 chunks with 500-token target
        assert len(chunks) >= 2
        assert all(c["token_count"] <= 700 for c in chunks)

    def test_chunk_text_maintains_ordering(self):
        sentence = "Sentence number placeholder goes here for testing purposes. "
        text = sentence * 50
        
        chunks = chunk_text(text, page_number=2)
        
        # Verify chunk_index is sequential
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i
            assert chunk["page_number"] == 2

    def test_chunk_text_creates_overlap(self):
        # Generate text with distinct sentences
        sentences = [f"This is sentence number {i}. " for i in range(100)]
        text = "".join(sentences)
        
        chunks = chunk_text(text, page_number=1)
        
        if len(chunks) >= 2:
            # Last ~50 tokens of chunk[0] should overlap with first ~50 tokens of chunk[1]
            chunk0_end = chunks[0]["text"][-200:]  # Last 200 chars
            chunk1_start = chunks[1]["text"][:200]  # First 200 chars
            
            # Should have some common content
            assert any(word in chunk1_start for word in chunk0_end.split()[-10:])

    def test_chunk_text_respects_token_cap(self):
        # Very long text that could exceed 700 tokens per chunk
        text = "word " * 1000  # ~1300 tokens
        
        chunks = chunk_text(text, page_number=1)
        
        # architecture.md §7.2: 700 hard cap
        for chunk in chunks:
            assert chunk["token_count"] <= 700

    def test_chunk_text_splits_at_sentence_boundaries(self):
        # Text with clear sentence structure
        text = ". ".join([f"Sentence {i}" for i in range(200)]) + "."
        
        chunks = chunk_text(text, page_number=1)
        
        # Each chunk should end with a period (sentence boundary)
        for chunk in chunks[:-1]:  # All except last
            assert chunk["text"].rstrip().endswith(".")

    def test_chunk_text_handles_no_page_number(self):
        # Plain text files have no page concept
        text = "This is plain text with no page numbers."
        chunks = chunk_text(text, page_number=None)
        
        assert chunks[0]["page_number"] is None

    def test_chunk_text_empty_input(self):
        chunks = chunk_text("", page_number=1)
        
        # Should return empty list, not a chunk with empty text
        assert len(chunks) == 0

    def test_chunk_text_whitespace_only(self):
        chunks = chunk_text("   \n\n   ", page_number=1)
        
        assert len(chunks) == 0
