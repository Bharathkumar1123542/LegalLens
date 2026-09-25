"""
Validation script for golden dataset annotations.
Ensures all annotation files conform to schema and reference valid documents.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

# Schema constants
VALID_CLAUSE_TYPES = {
    "termination", "payment_terms", "confidentiality", "liability",
    "intellectual_property", "warranty", "dispute_resolution", "renewal",
    "assignment", "force_majeure", "amendment", "notice", "severability",
    "entire_agreement", "non_compete", "severance", "return_of_materials",
    "remedies", "term_duration"
}

VALID_RISK_LEVELS = {"low", "medium", "high"}
VALID_MATERIALITY = {"none", "minor", "significant", "critical"}
VALID_READING_LEVELS = {"8th_grade", "high_school", "college"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}


def validate_annotation_file(annotation_path: Path, documents_dir: Path) -> List[str]:
    """Validate a single annotation file."""
    errors = []
    
    try:
        with open(annotation_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {annotation_path.name}: {e}"]
    except Exception as e:
        return [f"Error reading {annotation_path.name}: {e}"]
    
    # Required top-level fields
    required_fields = ["doc_id", "doc_type", "filename", "metadata", "clauses"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    if errors:
        return errors
    
    # Validate document file exists
    doc_path = documents_dir / data["filename"]
    if not doc_path.exists():
        errors.append(f"Document file not found: {data['filename']}")
    
    # Validate metadata
    metadata = data.get("metadata", {})
    required_metadata = ["jurisdiction", "year", "complexity", "word_count"]
    for field in required_metadata:
        if field not in metadata:
            errors.append(f"Missing metadata field: {field}")
    
    # Validate clauses
    clauses = data.get("clauses", [])
    if not clauses:
        errors.append("No clauses defined (at least one expected)")
    
    for i, clause in enumerate(clauses):
        clause_errors = validate_clause(clause, i)
        errors.extend(clause_errors)
    
    # Validate simplifications (optional but recommended)
    simplifications = data.get("simplifications", [])
    for i, simp in enumerate(simplifications):
        simp_errors = validate_simplification(simp, i)
        errors.extend(simp_errors)
    
    # Validate chat Q&A pairs (optional but recommended)
    qa_pairs = data.get("chat_qa_pairs", [])
    for i, qa in enumerate(qa_pairs):
        qa_errors = validate_qa_pair(qa, i)
        errors.extend(qa_errors)
    
    return errors


def validate_clause(clause: Dict, index: int) -> List[str]:
    """Validate a single clause."""
    errors = []
    prefix = f"Clause {index}"
    
    required = ["clause_id", "clause_type", "text_excerpt", "risk_level", "risk_rationale"]
    for field in required:
        if field not in clause:
            errors.append(f"{prefix}: Missing field '{field}'")
    
    if "clause_type" in clause and clause["clause_type"] not in VALID_CLAUSE_TYPES:
        errors.append(f"{prefix}: Invalid clause_type '{clause['clause_type']}'")
    
    if "risk_level" in clause and clause["risk_level"] not in VALID_RISK_LEVELS:
        errors.append(f"{prefix}: Invalid risk_level '{clause['risk_level']}'")
    
    if "text_excerpt" in clause:
        excerpt = clause["text_excerpt"]
        if len(excerpt) < 20:
            errors.append(f"{prefix}: text_excerpt too short (min 20 chars)")
        if len(excerpt) > 1000:
            errors.append(f"{prefix}: text_excerpt too long (max 1000 chars)")
    
    if "risk_rationale" in clause and len(clause["risk_rationale"]) < 10:
        errors.append(f"{prefix}: risk_rationale too brief (min 10 chars)")
    
    return errors


def validate_simplification(simp: Dict, index: int) -> List[str]:
    """Validate a simplification."""
    errors = []
    prefix = f"Simplification {index}"
    
    required = ["reading_level", "expected_grade", "simplified_text"]
    for field in required:
        if field not in simp:
            errors.append(f"{prefix}: Missing field '{field}'")
    
    if "reading_level" in simp and simp["reading_level"] not in VALID_READING_LEVELS:
        errors.append(f"{prefix}: Invalid reading_level '{simp['reading_level']}'")
    
    if "expected_grade" in simp:
        grade = simp["expected_grade"]
        if not isinstance(grade, (int, float)) or grade < 1 or grade > 18:
            errors.append(f"{prefix}: expected_grade must be between 1 and 18")
    
    return errors


def validate_qa_pair(qa: Dict, index: int) -> List[str]:
    """Validate a Q&A pair."""
    errors = []
    prefix = f"Q&A {index}"
    
    required = ["question", "expected_answer", "answer_must_include", "supporting_excerpts"]
    for field in required:
        if field not in qa:
            errors.append(f"{prefix}: Missing field '{field}'")
    
    if "difficulty" in qa and qa["difficulty"] not in VALID_DIFFICULTY:
        errors.append(f"{prefix}: Invalid difficulty '{qa['difficulty']}'")
    
    if "answer_must_include" in qa and not isinstance(qa["answer_must_include"], list):
        errors.append(f"{prefix}: answer_must_include must be a list")
    
    if "supporting_excerpts" in qa and not isinstance(qa["supporting_excerpts"], list):
        errors.append(f"{prefix}: supporting_excerpts must be a list")
    
    return errors


def main():
    """Validate all annotation files."""
    project_root = Path(__file__).parent.parent
    annotations_dir = project_root / "apps/api/tests/eval/golden_dataset/annotations"
    documents_dir = project_root / "apps/api/tests/eval/golden_dataset/documents"
    
    if not annotations_dir.exists():
        print(f"Annotations directory not found: {annotations_dir}")
        return 1
    
    if not documents_dir.exists():
        print(f"Documents directory not found: {documents_dir}")
        return 1
    
    annotation_files = list(annotations_dir.glob("*.json"))
    
    if not annotation_files:
        print("No annotation files found")
        return 1
    
    print(f"Validating {len(annotation_files)} annotation files...")
    print()
    
    all_errors = {}
    for annotation_path in sorted(annotation_files):
        errors = validate_annotation_file(annotation_path, documents_dir)
        if errors:
            all_errors[annotation_path.name] = errors
    
    if all_errors:
        print("❌ Validation failed with errors:\n")
        for filename, errors in all_errors.items():
            print(f"{filename}:")
            for error in errors:
                print(f"  - {error}")
            print()
        return 1
    else:
        print(f"✅ All {len(annotation_files)} annotation files are valid!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
