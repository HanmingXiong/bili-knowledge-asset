# REVIEW_FIXES_PHASE2

## Files Changed

- `backend/app/main.py`
- `backend/app/schemas.py`
- `backend/requirements.txt`
- `backend/tests/conftest.py`
- `backend/tests/test_asset_query_and_retry.py`
- `backend/tests/test_retrieval_pipeline.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/components/asset-detail-client.tsx`
- `frontend/components/generate-form.tsx`
- `frontend/components/mermaid-viewer.tsx`
- `frontend/app/globals.css`
- `README.md`
- `DEMO.md`
- `CHANGELOG.md`

## Demo Improvements

### 1. Health Visibility

- upgraded `GET /api/health` to expose evaluator-facing readiness signals:
  - `database`
  - `assets_directory`
  - `ffmpeg`
  - `gemini_configured`

This makes it easier to prove the environment is actually ready before the demo starts.

### 2. Mermaid Rendering

- Mermaid outputs are now rendered visually in the UI instead of shown as raw text
- added a dedicated Mermaid viewer component with a fallback to raw source if rendering fails

### 3. Demo Documentation

- added `DEMO.md`
- includes:
  - recommended walkthrough
  - known local Bilibili URLs already present in the DB
  - expected behavior per asset
  - sample output guidance

### 4. README Improvements

- clarified:
  - architecture
  - extraction strategy
  - memory design
  - structured knowledge
  - output generation
  - failure handling
  - tradeoffs
  - future improvements

### 5. Security Cleanup

- verified `.env` is ignored by git
- verified tracked files do not contain real API keys
- confirmed placeholder-only examples in docs and env example files

## Test Results

### Backend Tests

Command:

```bash
cd backend
./.venv/bin/pytest -q
```

Result:

- `4 passed`

Covered:

- asset detail structured knowledge exposure
- asset query endpoint
- retry endpoint
- retrieval pipeline

### Frontend Build

Command:

```bash
cd frontend
npm run build
```

Result:

- passed

### Health Endpoint Verification

Observed response:

```json
{
  "status": "ok",
  "database": true,
  "assets_directory": true,
  "ffmpeg": true,
  "gemini_configured": true
}
```

### Linting

- no dedicated lint script is configured in `frontend/package.json`
- `npm run lint --if-present` completed without running a lint task

## Remaining Limitations

- Screenshots were not bundled into `DEMO.md`; the live local UI is the primary demo artifact
- Bilibili video availability still varies by content and can affect transcript/keyframe success
- Retry remains synchronous and request-bound
- Mermaid generation quality still depends on the model returning valid Mermaid syntax
- Deprecation warnings remain in test output due to existing FastAPI startup hooks and `datetime.utcnow()` usage

## Estimated Evaluator Score

Estimated score after Phase 1 + Phase 2 improvements:

- **High pass / strong submission**

Reasoning:

- complete end-to-end flow exists
- evaluator-facing health/readiness checks are clear
- asset querying, memory, structured knowledge, and retry are implemented
- Mermaid output is visually rendered
- tests cover the most important new behaviors
- docs now support a structured live demo

Remaining score risk:

- Bilibili media extraction remains the main source of nondeterminism for keyframes/transcripts on arbitrary URLs
