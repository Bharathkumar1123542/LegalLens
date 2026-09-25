#!/bin/bash
# LegalLens Test Coverage Analysis Script
# Runs pytest with coverage reporting and generates detailed analysis

set -e

echo "🧪 LegalLens Test Coverage Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd apps/api

echo "📊 Running tests with coverage..."
echo ""

# Run tests with coverage
pytest \
  --cov=app \
  --cov-report=html \
  --cov-report=term-missing \
  --cov-report=json \
  -v \
  --tb=short

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Coverage report generated!"
echo ""
echo "📁 Reports available at:"
echo "   HTML: apps/api/htmlcov/index.html"
echo "   JSON: apps/api/coverage.json"
echo ""
echo "💡 Open HTML report:"
echo "   Windows: start apps/api/htmlcov/index.html"
echo "   Mac:     open apps/api/htmlcov/index.html"
echo "   Linux:   xdg-open apps/api/htmlcov/index.html"
echo ""

# Parse coverage percentage from JSON
if [ -f coverage.json ]; then
    COVERAGE=$(python3 -c "import json; data=json.load(open('coverage.json')); print(f\"{data['totals']['percent_covered']:.1f}\")")
    echo "📈 Current Coverage: ${COVERAGE}%"
    
    TARGET=80
    if (( $(echo "$COVERAGE >= $TARGET" | bc -l) )); then
        echo "✅ Target coverage (${TARGET}%) achieved!"
    else
        GAP=$(python3 -c "print(f'{${TARGET} - ${COVERAGE}:.1f}')")
        echo "⚠️  Coverage gap: ${GAP}% below target (${TARGET}%)"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
