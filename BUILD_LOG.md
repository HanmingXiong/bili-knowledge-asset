# BUILD_LOG

## What Works

- FastAPI backend scaffolded with the required endpoints
- SQLite persistence for assets, transcript chunks, keyframes, and generated outputs
- Local file storage under `data/assets/{bvid}/`
- BVID parsing from Bilibili URLs
- Metadata fetch from the required Bilibili API
- Subtitle extraction attempt through Bilibili subtitle APIs
- Video download attempt via Bilibili play URL, then `yt-dlp` fallback
- Keyframe extraction via `ffmpeg` when available
- Gemini text + vision service abstraction in `backend/app/services/llm.py`
- Local fallback generation when Gemini is unavailable or fails
- Next.js frontend with:
  - home page
  - asset detail page
  - multi-asset generate page
- Generated outputs persisted and shown on asset detail pages

## What Is Partial

- Subtitle availability depends on what Bilibili exposes for a given video
- Direct Bilibili playable URLs may fail for some content; `yt-dlp` is the fallback
- Keyframes require `ffmpeg`; in the current workspace, `ffmpeg` is not installed
- Gemini image descriptions and structured notes require a valid `GOOGLE_API_KEY`
- Mermaid output is supported, but rendered as code text rather than as a live diagram widget

## Known Limitations

- Asset extraction is synchronous inside `POST /api/assets/create`
- No explicit retry endpoint for failed extraction stages
- No audio transcription fallback when subtitles are unavailable
- No ChromaDB integration; retrieval is keyword/chunk based
- Existing BVIDs are deduplicated and return the stored asset instead of re-extracting
- Frontend rendering is intentionally lightweight and does not include markdown parsing

## How To Demo It

1. Install backend dependencies and run FastAPI on port `8000`.
2. Install frontend dependencies and run Next.js on port `3000`.
3. Set `GOOGLE_API_KEY` if you want Gemini-backed descriptions and notes.
4. Install `ffmpeg` if you want visual keyframe extraction.
5. Paste a public Bilibili URL on the home page.
6. Open the created asset and show:
   - metadata
   - transcript status/chunks
   - keyframes if available
   - structured notes
   - generated outputs
7. Generate an `Illustrated Summary` and an `Understanding Quiz`.
8. If a step fails, point to the `partial_ready` status and the stored asset data to show graceful degradation.

## Local Verification Performed

- `python3 -m compileall backend` completed successfully
- `node` and `npm` are available in the workspace
- `ffmpeg` is not currently installed in the workspace shell
- TypeScript CLI is not globally installed, so frontend type-checking was not run before dependency installation
