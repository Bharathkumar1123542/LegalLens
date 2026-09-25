# LegalLens Test Coverage Baseline

**Date**: 2025-01-19  
**Phase**: Phase 7 - Testing & Quality  
**Status**: Baseline Established

---

## Current Test Coverage (Estimated)

Based on implemented test files and modules:

| Phase | Module | Test File | Coverage Est. | Status |
|-------|--------|-----------|---------------|--------|
| **Phase 0** | | | | |
| 0 | config.py | test_config.py | ~100% | ✅ 24 tests |
| **Phase 1** | | | | |
| 1 | security.py | test_security.py | ~95% | ✅ 22 tests |
| 1 | auth service | test_auth_service.py | ~90% | ✅ 15 tests |
| 1 | ingestion service | test_ingestion_service.py | ~85% | ✅ 12 tests |
| 1 | audit service | test_audit_service.py | ~90% | ✅ 7 tests |
| 1 | storage service | *missing* | ~0% | ❌ Need tests |
| 1 | auth endpoints | test_auth_endpoints.py | ~95% | ✅ 11 tests |
| 1 | document endpoints | test_document_endpoints.py | ~90% | ✅ 13 tests |
| **Phase 2** | | | | |
| 2 | text_extraction.py | test_text_extraction.py | ~90% | ✅ 11 tests |
| 2 | ocr.py | test_ocr.py | ~85% | ✅ 7 tests |
| 2 | chunking.py | test_chunking.py | ~95% | ✅ 13 tests |
| 2 | embedding.py | test_embedding.py | ~90% | ✅ 11 tests |
| 2 | ingestion pipeline | test_ingestion_pipeline.py | ~80% | ✅ 3 tests |
| **Phase 3** | | | | |
| 3 | llm_orchestration.py | test_llm_orchestration.py | ~90% | ✅ 19 tests |
| 3 | simplification.py | test_simplification.py | ~85% | ✅ 14 tests |
| 3 | clause_extraction.py | test_clause_extraction.py | ~90% | ✅ 14 tests |
| 3 | phase 3 flow | test_phase3_flow.py | ~75% | ✅ 4 tests |
| **Phase 4** | | | | |
| 4 | chat.py | test_chat.py | ~85% | ✅ 16 tests |
| 4 | chat flow | test_chat_flow.py | ~80% | ✅ 7 tests |
| **Phase 5** | | | | |
| 5 | comparison.py | *missing* | ~0% | ❌ Need tests |
| 5 | export.py | *missing* | ~30% | ⚠️ Partial (workers call it) |
| 5 | comparison flow | *missing* | ~0% | ❌ Need tests |
| 5 | export flow | *missing* | ~0% | ❌ Need tests |
| **Phase 6** | | | | |
| 6 | workers/__init__.py | *missing* | ~0% | ❌ Need tests |
| 6 | ingestion_worker.py | *implicit* | ~50% | ⚠️ Tested via pipeline |
| 6 | extraction_worker.py | *missing* | ~0% | ❌ Need tests |
| 6 | embedding_worker.py | *missing* | ~0% | ❌ Need tests |
| 6 | comparison_worker.py | *missing* | ~0% | ❌ Need tests |
| 6 | export_worker.py | *missing* | ~0% | ❌ Need tests |
| 6 | renderers/pdf_renderer.py | *missing* | ~0% | ❌ Need tests |
| 6 | renderers/docx_renderer.py | *missing* | ~0% | ❌ Need tests |

---

## Test Statistics

**Total Tests Written**: 183 tests
- Unit tests: 159
- Integration tests: 24
- E2E tests: 0 (to be created)
- Evaluation tests: 0 (to be created)
- Performance tests: 0 (to be created)

**Estimated Overall Coverage**: ~60-65%

**Target**: 80%

**Gap**: ~15-20 percentage points

---

## Coverage Gaps Identified

### High Priority (0-50% coverage)
1. **storage.py** (0%) - S3 operations, presigned URLs
   - Need: `test_storage.py` with ~10 tests
   - Functions: upload_to_s3, download_from_s3, delete_from_s3, generate_presigned_url
   
2. **comparison.py** (0%) - Clause alignment, materiality rating
   - Need: `test_comparison.py` with ~15 tests
   - Functions: create_comparison_job, run_comparison, _align_clauses_by_type
   
3. **export.py** (30%) - Export generation, format rendering
   - Need: `test_export.py` with ~15 tests
   - Functions: generate_export, _generate_document_export, _generate_comparison_export
   
4. **All 6 workers** (0-50%) - Celery task execution
   - Need: Worker-specific unit tests
   - Focus: Task logic, error handling, status transitions

5. **Renderers** (0%) - PDF/DOCX generation
   - Need: `test_pdf_renderer.py` and `test_docx_renderer.py`
   - Test: Markdown parsing, formatting, output validation

### Medium Priority (50-70% coverage)
6. **API endpoint error cases** - Some error paths untested
7. **Edge cases in services** - Boundary conditions, race conditions

### Low Priority (70-80% coverage)
8. **Models** - ORM validation, relationship loading (mostly covered by integration tests)
9. **Schemas** - Pydantic validation (mostly covered by endpoint tests)

---

## Test Files to Create

### Phase 7 Priority Order

**Week 1: Critical Coverage Gaps**
1. `tests/unit/test_storage.py` - 10 tests (S3 operations)
2. `tests/unit/test_comparison.py` - 15 tests (clause alignment)
3. `tests/unit/test_export.py` - 15 tests (export generation)
4. `tests/integration/test_comparison_flow.py` - 8 tests (comparison endpoints)
5. `tests/integration/test_export_flow.py` - 8 tests (export endpoints)

**Week 2: Worker Coverage**
6. `tests/unit/test_extraction_worker.py` - 8 tests
7. `tests/unit/test_embedding_worker.py` - 6 tests
8. `tests/unit/test_comparison_worker.py` - 10 tests
9. `tests/unit/test_export_worker.py` - 10 tests

**Week 3: Renderer & E2E**
10. `tests/unit/test_pdf_renderer.py` - 12 tests
11. `tests/unit/test_docx_renderer.py` - 12 tests
12. `tests/integration/test_e2e_journey.py` - 5 tests (full user journey)

**Week 4: Evaluation & Performance**
13. `tests/eval/test_llm_quality.py` - Golden dataset evaluation
14. `tests/performance/test_latency.py` - Latency benchmarks
15. `tests/performance/locustfile.py` - Load testing

---

## Tools Created

### Coverage Analysis Tools
1. **scripts/test-coverage.sh** - Bash script to run pytest with coverage
2. **scripts/test-coverage.ps1** - PowerShell script (Windows)
3. **scripts/analyze-coverage-gaps.py** - Detailed gap analysis with suggestions

### Usage
```bash
# Run coverage analysis
./scripts/test-coverage.sh

# Analyze gaps and get suggestions
python scripts/analyze-coverage-gaps.py

# Open HTML report
open apps/api/htmlcov/index.html
```

---

## Next Steps

### Immediate (Task 7.2-7.4)
1. Create `test_storage.py` with comprehensive S3 operation tests
2. Create `test_comparison.py` with clause alignment and materiality tests
3. Create `test_export.py` with format rendering and generation tests

### Short-term (Task 7.5-7.6)
4. Create integration tests for Phase 5 (comparison/export flow)
5. Create E2E test for complete user journey

### Medium-term (Task 7.7-7.9)
6. Build golden dataset structure
7. Implement LLM evaluation harness
8. Create performance test suite with locust

### Continuous
- Run coverage after each new test file
- Track progress toward 80% goal
- Update this document with actual coverage numbers

---

## Success Criteria

**Phase 7 Complete** when:
- ✅ Overall test coverage ≥ 80%
- ✅ All critical modules (storage, comparison, export, workers) have tests
- ✅ Integration tests cover all Phase 5 endpoints
- ✅ E2E test validates complete user journey
- ✅ Golden dataset created with 50+ annotated documents
- ✅ LLM evaluation harness validates quality metrics
- ✅ Performance tests validate latency targets

**Timeline**: 3-4 weeks for complete Phase 7 implementation

---

## References

- Test suite documentation: `apps/api/tests/README.md`
- Coverage scripts: `scripts/test-coverage.*`
- Gap analysis tool: `scripts/analyze-coverage-gaps.py`
- Progress tracker: `.context/progress-tracker.md`
- Implementation plan: `.context/implementation-plan.md`
