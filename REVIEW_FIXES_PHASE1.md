# REVIEW_FIXES_PHASE1

## Files Changed

- `backend/app/db.py`
- `backend/app/models.py`
- `backend/app/routers/assets.py`
- `backend/app/schemas.py`
- `backend/app/services/extraction.py`
- `backend/app/services/llm.py`
- `backend/app/services/retrieval.py`
- `backend/app/services/video.py`
- `frontend/app/globals.css`
- `frontend/components/asset-detail-client.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`

## Features Added

### 1. Asset Querying

- Added `POST /api/assets/{asset_id}/query`
- Queries now search:
  - transcript chunks
  - visual descriptions
  - structured knowledge
  - metadata-derived snippets
- Gemini answers are grounded in retrieved evidence
- Response includes:
  - `answer`
  - `evidence`
  - `timestamps`
- Added `Ask This Asset` section on the asset detail page

### 2. Memory / RAG

- Added SQLite-backed `asset_snippets` storage
- Added SQLite FTS5 virtual table and triggers
- Snippets are populated from:
  - transcript chunks
  - visual descriptions
  - structured knowledge
  - metadata summary
- Generation and asset querying now use FTS retrieval first, with local fallback retrieval if needed
- Added snippet visibility on the asset page to make indexed memory inspectable

### 3. Structured Knowledge

- Replaced freeform notes with structured JSON stored in `structured_notes.json`
- Structured schema now includes:
  - `summary`
  - `facts`
  - `opinions`
  - `arguments`
  - `timeline`
  - `concepts`
  - `causal_chains`
  - `visual_evidence`
- Gemini now generates this JSON directly
- API exposes structured knowledge on asset detail responses
- Frontend displays structured knowledge in sectioned form

### 4. Retry Functionality

- Added `POST /api/assets/{asset_id}/retry`
- Supported retry stages:
  - `transcript`
  - `keyframes`
  - `vision`
  - `notes`
  - `all`
- Added `Retry Extraction` controls on the asset detail page
- Retry updates the stored asset and refreshes snippet memory

## Test Results

### Backend Verification

- `backend/.venv/bin/python -m compileall backend/app`
  - passed

### API Smoke Test

Executed via FastAPI `TestClient`:

- `GET /api/health` -> `200`
- `GET /api/assets` -> `200`
- `GET /api/assets/{asset_id}` -> `200`
- `POST /api/assets/{asset_id}/query` -> `200`
- `POST /api/assets/{asset_id}/retry` with `notes` -> `200`

Observed smoke-test state:

- indexed snippet count populated
- structured summary present in API response
- query endpoint returned expected keys

### Frontend Verification

- `npm run build`
  - passed

## Remaining Limitations

- Retry is synchronous and runs inside the request cycle
- Existing assets that were extracted before these changes may need one retry pass to fully refresh structured knowledge and snippet memory
- FTS retrieval is lightweight and asset-local; it does not yet do cross-asset ranking beyond the selected asset set
- Transcript availability still depends on Bilibili subtitle availability
- Keyframe success still depends on getting a decodable downloadable video stream
- Vision retry requires existing keyframes; if none exist, keyframes or full retry must run first
