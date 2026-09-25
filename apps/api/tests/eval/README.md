# LegalLens Evaluation Suite

This directory contains the evaluation harness for testing LLM quality in LegalLens.

## Structure

```
eval/
├── golden_dataset/          # Annotated legal documents for evaluation
│   ├── documents/          # Sample legal documents (PDF/text)
│   ├── annotations/        # Ground truth annotations (JSON)
│   └── README.md          # Dataset documentation
├── test_llm_quality.py     # LLM evaluation tests
└── README.md              # This file
```

## Golden Dataset

The golden dataset contains 50 annotated legal documents covering common contract types:
- Employment agreements (10 documents)
- Non-disclosure agreements (10 documents)
- Service agreements (10 documents)
- Lease agreements (10 documents)
- Sales agreements (10 documents)

Each document includes:
- **Document text**: Plain text or PDF
- **Ground truth clauses**: Manually annotated clauses with type, risk level, excerpts
- **Expected simplifications**: Pre-approved simplified versions for reading levels
- **Chat Q&A pairs**: Questions with verified correct answers
- **Comparison ground truth**: For document pairs, expected differences and materiality

## Evaluation Metrics

### 1. Clause Extraction Quality
- **Precision**: % of extracted clauses that are correct
- **Recall**: % of true clauses that were extracted
- **F1 Score**: Harmonic mean of precision and recall
- **Risk Level Accuracy**: % of clauses with correct risk assessment

### 2. Chat/Q&A Quality
- **Groundedness**: % of answers supported by document content
- **Correctness**: % of answers matching ground truth
- **Completeness**: % of relevant information included

### 3. Comparison Quality
- **Difference Detection**: % of true differences identified
- **Materiality Accuracy**: % of correct materiality ratings
- **False Positives**: % of incorrect differences flagged

### 4. Simplification Quality
- **Reading Level**: Target reading level achieved (Flesch-Kincaid)
- **Accuracy**: Meaning preserved vs. original
- **Clarity**: Simplified text is understandable

## Running Evaluations

```bash
# Run full evaluation suite
pytest apps/api/tests/eval/test_llm_quality.py -v

# Run specific evaluation
pytest apps/api/tests/eval/test_llm_quality.py::TestClauseExtractionQuality -v

# Generate evaluation report
pytest apps/api/tests/eval/test_llm_quality.py --json-report --json-report-file=eval_report.json
```

## Adding New Test Cases

1. Add document to `golden_dataset/documents/`
2. Create annotation file in `golden_dataset/annotations/` (see schema below)
3. Run evaluation to verify

## Annotation Schema

See `golden_dataset/README.md` for detailed annotation schema.

## Quality Targets

Per architecture.md and implementation-plan.md:
- **Clause Extraction F1**: ≥ 0.85
- **Chat Groundedness**: ≥ 0.90
- **Comparison Accuracy**: ≥ 0.80
- **Risk Assessment Accuracy**: ≥ 0.75

## Notes

- Annotations created by legal professionals or verified legal AI
- Dataset covers common clauses and edge cases
- Regular updates as new clause types discovered
- Privacy: All documents sanitized, no real PII
