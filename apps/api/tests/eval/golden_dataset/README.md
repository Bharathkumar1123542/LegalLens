# Golden Dataset for LegalLens Evaluation

This dataset contains 50 manually annotated legal documents for evaluating LLM quality.

## Dataset Structure

Each document has two files:
1. **Document file**: `documents/{doc_id}.txt` or `documents/{doc_id}.pdf`
2. **Annotation file**: `annotations/{doc_id}.json`

## Annotation Schema

```json
{
  "doc_id": "employment_001",
  "doc_type": "employment_agreement",
  "filename": "employment_001.txt",
  "metadata": {
    "jurisdiction": "California",
    "year": 2024,
    "complexity": "medium",
    "page_count": 8,
    "word_count": 2500
  },
  "clauses": [
    {
      "clause_id": "c1",
      "clause_type": "termination",
      "text_excerpt": "Either party may terminate this agreement with 30 days written notice.",
      "start_char": 1250,
      "end_char": 1340,
      "risk_level": "medium",
      "risk_rationale": "Short termination notice may not allow adequate transition time.",
      "legal_significance": "Standard termination provision with minimal notice period."
    }
  ],
  "simplifications": [
    {
      "reading_level": "8th_grade",
      "expected_grade": 8.0,
      "simplified_text": "You or your employer can end this job with 30 days notice in writing.",
      "key_terms": ["termination", "notice period"],
      "citations": [
        {
          "original": "30 days written notice",
          "location": "Section 12, Termination"
        }
      ]
    }
  ],
  "chat_qa_pairs": [
    {
      "question": "How much notice do I need to quit?",
      "expected_answer": "You need to give 30 days written notice to terminate the employment.",
      "answer_must_include": ["30 days", "written notice"],
      "supporting_excerpts": ["Either party may terminate this agreement with 30 days written notice."],
      "difficulty": "easy"
    }
  ],
  "comparison_ground_truth": [
    {
      "compare_with_doc_id": "employment_002",
      "expected_differences": [
        {
          "clause_type": "termination",
          "diff_summary": "Document 001 requires 30 days notice, document 002 requires 60 days.",
          "materiality": "significant",
          "rationale": "Longer notice period provides more protection for employer."
        }
      ]
    }
  ]
}
```

## Field Descriptions

### Document Metadata
- **doc_id**: Unique identifier (e.g., "employment_001")
- **doc_type**: Contract category (employment_agreement, nda, service_agreement, etc.)
- **filename**: Source document filename
- **metadata**: Document characteristics for filtering/analysis

### Clauses
- **clause_id**: Unique identifier within document
- **clause_type**: Standardized clause category (see clause types below)
- **text_excerpt**: Exact text from document (200-500 chars)
- **start_char/end_char**: Character positions in original text
- **risk_level**: "low", "medium", "high" based on business risk
- **risk_rationale**: Why this risk level (1-2 sentences)
- **legal_significance**: Legal context (optional)

### Simplifications
- **reading_level**: Target level (8th_grade, high_school, college)
- **expected_grade**: Flesch-Kincaid grade level (numeric)
- **simplified_text**: Ground truth simplified version
- **key_terms**: Important terms that must be preserved
- **citations**: Links back to original document

### Chat Q&A Pairs
- **question**: User question about document
- **expected_answer**: Correct answer (1-3 sentences)
- **answer_must_include**: Required phrases/facts
- **supporting_excerpts**: Document text supporting answer
- **difficulty**: "easy", "medium", "hard"

### Comparison Ground Truth
- **compare_with_doc_id**: ID of document to compare against
- **expected_differences**: List of known differences
- **diff_summary**: Human-verified difference description
- **materiality**: "none", "minor", "significant", "critical"
- **rationale**: Why this materiality level

## Clause Types

Standardized clause types used in annotations:
- **termination**: Contract termination provisions
- **payment_terms**: Payment amounts, schedules, methods
- **confidentiality**: NDA and confidentiality obligations
- **liability**: Liability caps, limitations, indemnification
- **intellectual_property**: IP ownership and licensing
- **warranty**: Warranties and disclaimers
- **dispute_resolution**: Arbitration, governing law, jurisdiction
- **renewal**: Auto-renewal and renewal terms
- **assignment**: Assignment and delegation restrictions
- **force_majeure**: Force majeure provisions
- **amendment**: How contract can be amended
- **notice**: Notice requirements and methods
- **severability**: Severability clauses
- **entire_agreement**: Integration/merger clauses

## Risk Level Guidelines

### Low Risk
- Standard boilerplate clauses
- Industry-standard terms
- Minimal business impact
- Easy to comply with

### Medium Risk
- Shorter-than-usual time periods
- Moderate financial exposure
- Some compliance burden
- Common but worth reviewing

### High Risk
- Unusual or one-sided terms
- Significant financial exposure
- Difficult compliance requirements
- Could impact business operations

## Quality Standards

All annotations must:
1. Be reviewed by legal professional or verified AI
2. Include complete clause excerpts (not truncated)
3. Have accurate character positions
4. Use consistent clause types from approved list
5. Include risk rationale (not just risk level)

## Document Sourcing

- Anonymized real contracts (PII removed)
- Synthetic contracts generated with Claude
- Public domain legal templates
- Open-source contract examples

All documents sanitized:
- Names replaced with placeholders (e.g., "EMPLOYEE", "COMPANY")
- Addresses replaced with generic locations
- Dollar amounts adjusted to round numbers
- Dates standardized to 2024

## Adding New Documents

1. Create document file in `documents/`
2. Create annotation JSON in `annotations/`
3. Validate schema: `python scripts/validate_annotations.py`
4. Run test suite to verify: `pytest tests/eval/test_llm_quality.py`
5. Update this README if adding new clause types

## Sample Documents

Initial dataset (50 documents):

### Employment Agreements (10)
- employment_001 through employment_010
- Various notice periods, compensation structures, non-compete clauses

### NDAs (10)
- nda_001 through nda_010
- Mutual and unilateral NDAs, varying confidentiality periods

### Service Agreements (10)
- service_001 through service_010
- Consulting, SaaS, and professional services contracts

### Lease Agreements (10)
- lease_001 through lease_010
- Commercial and residential leases, varying terms

### Sales Agreements (10)
- sales_001 through sales_010
- Product sales, purchase orders, warranty terms

## Version History

- **v1.0** (2026-09): Initial dataset with 50 documents
- Future: Expand to 100+ documents with edge cases
