# CHANGELOG

## Final Polish

### Added

- polished landing page with clearer product positioning and feature cards
- stronger asset detail information hierarchy with reusable-asset framing
- clearer query evidence presentation
- improved generator experience for output modes and cross-asset querying
- final submission docs in `FINAL_POLISH.md`

### Changed

- README rewritten to match the final product flow, current feature set, and local setup
- DEMO guide rewritten around a clean evaluator walkthrough and troubleshooting
- `.gitignore` expanded for local env and cache hygiene

### Verification

- backend tests pass
- frontend production build passes

## Phase 2

### Added

- evaluator-oriented `/api/health` diagnostics
- visual Mermaid rendering in the frontend
- `DEMO.md` with recommended flow, known local URLs, expected behaviors, and sample output guidance
- targeted backend tests for:
  - asset query endpoint
  - retry endpoint
  - structured knowledge exposure
  - retrieval pipeline / FTS-backed snippet search

### Changed

- README rewritten around the current product behavior
- frontend generation and asset detail views now render Mermaid outputs visually
- backend requirements now include `pytest`
- frontend dependencies now include `mermaid`

### Security

- verified `.env` is gitignored
- verified tracked files do not contain real API keys
- confirmed README and `.env.example` use placeholders

### Verification

- backend tests pass
- frontend production build passes
- health endpoint returns full readiness payload

## Phase 1

- added per-asset querying
- added SQLite FTS-backed snippet memory
- added structured knowledge JSON
- added stage-specific retry functionality
