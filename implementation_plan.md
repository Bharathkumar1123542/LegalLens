# LegalLens — Build Plan

## Current Phase: Phase 0 — Scaffolding

### Situation
- Context files exist in `.context/` 
- Prior scaffold from `progress-tracker.md` was built in a different sandbox and not persisted
- All six context files read; proceeding per `ai-workflow-rules.md` operating rule 1

### UI Design System Decision (surfaced per `ui-context.md`)
Using **Tailwind CSS defaults — slate/indigo neutral theme** as an explicit placeholder (option 2 from `ui-context.md`). 
This is NOT a locked-in design system. Declared default to unblock UI work. Will update `ui-context.md`.

### Build Order
1. Full folder structure scaffold (empty placeholder files)
2. `infra/docker-compose.yml`
3. `.env.example`
4. `apps/api` — FastAPI shell (main.py, config, health endpoint, Dockerfile, requirements.txt)
5. `apps/web` — Next.js shell (package.json, next.config.js, layout, page, tailwind config)
6. `.github/workflows/ci.yml`
7. `README.md`
8. Phase 0 tests
9. Update `progress-tracker.md`

### Phase 0 Exit Criteria (from `ai-workflow-rules.md`)
- `docker compose up` succeeds
- Health-check endpoint returns 200
