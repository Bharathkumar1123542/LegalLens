# LegalLens Test Coverage Analysis Script (PowerShell)
# Runs pytest with coverage reporting and generates detailed analysis

$ErrorActionPreference = "Stop"

Write-Host "🧪 LegalLens Test Coverage Analysis" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

Set-Location apps\api

Write-Host "📊 Running tests with coverage..." -ForegroundColor Yellow
Write-Host ""

# Run tests with coverage
pytest `
  --cov=app `
  --cov-report=html `
  --cov-report=term-missing `
  --cov-report=json `
  -v `
  --tb=short

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Coverage report generated!" -ForegroundColor Green
Write-Host ""
Write-Host "📁 Reports available at:" -ForegroundColor White
Write-Host "   HTML: apps\api\htmlcov\index.html"
Write-Host "   JSON: apps\api\coverage.json"
Write-Host ""
Write-Host "💡 Open HTML report:" -ForegroundColor White
Write-Host "   Invoke-Item apps\api\htmlcov\index.html"
Write-Host ""

# Parse coverage percentage from JSON
if (Test-Path "coverage.json") {
    $coverageData = Get-Content "coverage.json" | ConvertFrom-Json
    $coverage = [math]::Round($coverageData.totals.percent_covered, 1)
    
    Write-Host "📈 Current Coverage: $coverage%" -ForegroundColor Cyan
    
    $target = 80
    if ($coverage -ge $target) {
        Write-Host "✅ Target coverage ($target%) achieved!" -ForegroundColor Green
    } else {
        $gap = [math]::Round($target - $coverage, 1)
        Write-Host "⚠️  Coverage gap: $gap% below target ($target%)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
