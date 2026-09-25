#!/usr/bin/env python3
"""
Coverage Gap Analysis Tool
Analyzes coverage.json and identifies modules needing tests
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_coverage_data(coverage_file: Path) -> Dict:
    """Load coverage data from JSON file."""
    with open(coverage_file) as f:
        return json.load(f)


def analyze_gaps(coverage_data: Dict, threshold: float = 80.0) -> List[Tuple[str, float, int, int]]:
    """
    Analyze coverage gaps and return modules below threshold.
    
    Returns list of (module_name, coverage_pct, covered_lines, total_lines)
    sorted by coverage percentage (lowest first).
    """
    gaps = []
    
    for file_path, file_data in coverage_data['files'].items():
        # Skip __init__.py and test files
        if '__init__' in file_path or '/tests/' in file_path:
            continue
        
        # Calculate coverage percentage
        summary = file_data['summary']
        covered = summary['covered_lines']
        total = summary['num_statements']
        
        if total == 0:
            continue
        
        coverage_pct = (covered / total) * 100
        
        # Extract module name
        module_name = file_path.replace('app/', '').replace('.py', '').replace('/', '.')
        
        # Add to gaps if below threshold
        if coverage_pct < threshold:
            gaps.append((module_name, coverage_pct, covered, total))
    
    # Sort by coverage percentage (lowest first)
    gaps.sort(key=lambda x: x[1])
    
    return gaps


def print_gap_analysis(gaps: List[Tuple[str, float, int, int]], threshold: float):
    """Print formatted gap analysis."""
    print("\n" + "="*80)
    print(f"📊 COVERAGE GAP ANALYSIS (Threshold: {threshold}%)")
    print("="*80 + "\n")
    
    if not gaps:
        print(f"✅ All modules meet the {threshold}% coverage threshold!\n")
        return
    
    print(f"Found {len(gaps)} modules below {threshold}% coverage:\n")
    print(f"{'Module':<50} {'Coverage':<12} {'Lines':<15}")
    print("-" * 80)
    
    for module, coverage_pct, covered, total in gaps:
        coverage_str = f"{coverage_pct:5.1f}%"
        lines_str = f"{covered}/{total}"
        
        # Color code by severity
        if coverage_pct < 50:
            marker = "🔴"
        elif coverage_pct < 70:
            marker = "🟠"
        else:
            marker = "🟡"
        
        print(f"{marker} {module:<47} {coverage_str:<12} {lines_str:<15}")
    
    print("\n" + "="*80 + "\n")


def suggest_test_files(gaps: List[Tuple[str, float, int, int]]):
    """Suggest test files to create/enhance."""
    print("💡 SUGGESTED TEST FILES TO CREATE/ENHANCE:\n")
    
    suggested = set()
    for module, coverage_pct, _, _ in gaps:
        # Extract service/module category
        parts = module.split('.')
        
        if len(parts) >= 2:
            category = parts[0]  # services, api, models, etc.
            name = parts[1]
            
            if category == 'services':
                test_file = f"tests/unit/test_{name}.py"
            elif category == 'api':
                test_file = f"tests/integration/test_{name}_endpoints.py"
            elif category == 'workers':
                test_file = f"tests/unit/test_{name}_worker.py"
            else:
                test_file = f"tests/unit/test_{category}_{name}.py"
            
            suggested.add((test_file, module, coverage_pct))
    
    # Sort by coverage (lowest first)
    suggested_sorted = sorted(suggested, key=lambda x: x[2])
    
    for i, (test_file, module, coverage_pct) in enumerate(suggested_sorted[:10], 1):
        priority = "HIGH" if coverage_pct < 50 else "MEDIUM" if coverage_pct < 70 else "LOW"
        print(f"{i:2}. [{priority:6}] {test_file:<45} (covers: {module})")
    
    if len(suggested) > 10:
        print(f"\n   ... and {len(suggested) - 10} more files")
    
    print("\n" + "="*80 + "\n")


def main():
    # Find coverage.json
    coverage_file = Path("apps/api/coverage.json")
    
    if not coverage_file.exists():
        print("❌ coverage.json not found!")
        print("   Run: pytest --cov=app --cov-report=json")
        sys.exit(1)
    
    # Load and analyze
    coverage_data = load_coverage_data(coverage_file)
    
    # Print overall summary
    totals = coverage_data['totals']
    overall_coverage = totals['percent_covered']
    
    print("\n" + "="*80)
    print("📈 OVERALL COVERAGE SUMMARY")
    print("="*80)
    print(f"  Total Lines:     {totals['num_statements']}")
    print(f"  Covered Lines:   {totals['covered_lines']}")
    print(f"  Missing Lines:   {totals['missing_lines']}")
    print(f"  Coverage:        {overall_coverage:.1f}%")
    print(f"  Target:          80.0%")
    
    if overall_coverage >= 80:
        print(f"  Status:          ✅ TARGET MET")
    else:
        gap = 80 - overall_coverage
        print(f"  Gap:             ⚠️  {gap:.1f}% below target")
    
    print("="*80)
    
    # Analyze gaps
    threshold = 80.0
    gaps = analyze_gaps(coverage_data, threshold)
    
    # Print gap analysis
    print_gap_analysis(gaps, threshold)
    
    # Suggest test files
    if gaps:
        suggest_test_files(gaps)
    
    # Exit code based on target
    sys.exit(0 if overall_coverage >= 80 else 1)


if __name__ == "__main__":
    main()
