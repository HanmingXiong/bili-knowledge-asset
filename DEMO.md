# Demo Guide

## Recommended Demo Script

Use the demo as a clear product story:

1. Start the backend.
2. Start the frontend.
3. Open the home page.
4. Paste a public Bilibili URL.
5. Create the asset.
6. Open the saved asset.
7. Show:
   - metadata
   - transcript source and chunks
   - keyframes and visual descriptions
   - structured knowledge
   - memory snippets
8. Ask the asset a question.
9. Generate an Illustrated Summary.
10. Generate an Understanding Quiz.
11. Generate a Mermaid Mind Map.
12. Open the generator page and run a multi-asset query or output.
13. Retry a failed stage if the asset is `partial_ready`.

## Known-Good Demo Workflow

### Start Backend

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Start Frontend

```bash
cd frontend
npm run dev
```

### Demo the Product

1. Home page:
   show the hero, URL input, and asset library
2. Create asset:
   paste a public Bilibili URL and click `Create Reusable Asset`
3. Asset detail:
   show the evidence-backed asset structure
4. Ask question:
   use `Ask This Asset`
5. Illustrated Summary:
   show how the asset becomes reusable notes
6. Understanding Quiz:
   show study value
7. Mermaid Mind Map:
   show structural abstraction
8. Multi-asset generation:
   show comparison or combined output
9. Retry Extraction:
   show resilience if transcript, vision, or notes are incomplete

## Suggested Questions

- `What are the main arguments?`
- `What facts were extracted?`
- `What visual evidence supports the main point?`
- `What does this asset emphasize compared with the other one?`

## Expected Outputs

### Illustrated Summary

Expected characteristics:

- sectioned output
- grounded in transcript, visual evidence, and structured knowledge
- timestamps when available
- explicit fallback language when evidence is incomplete

### Understanding Quiz

Expected characteristics:

- multiple-choice questions
- short-answer questions
- answer key
- evidence-grounded prompts

### Mermaid Mind Map

Expected characteristics:

- visually rendered in the frontend when Mermaid succeeds
- fallback to raw Mermaid text only if rendering fails

## Expected Extraction Behavior

### Best Case

- metadata succeeds
- subtitles succeed or Gemini ASR fills the gap
- video download succeeds
- keyframes succeed
- Gemini generates visual descriptions and structured knowledge
- asset lands in `ready`

### Partial Case

- metadata succeeds
- transcript missing or limited
- keyframes missing or incomplete
- Gemini or download step falls back
- asset lands in `partial_ready`
- query and generation still work

## Troubleshooting

### `ffmpeg` missing

Symptoms:

- no keyframes
- no ASR fallback audio extraction

Fix:

- install `ffmpeg`
- restart the backend

### Gemini key missing

Symptoms:

- health endpoint shows `gemini_configured: false`
- structured knowledge and generation quality drop

Fix:

- set `GOOGLE_API_KEY` in `.env`
- restart the backend

### Bilibili download unavailable

Symptoms:

- metadata succeeds
- keyframes fail
- asset becomes `partial_ready`

Fix:

- use a different public video
- retry `keyframes` or `all`

### No subtitles

Symptoms:

- transcript unavailable from subtitles

Behavior:

- Gemini ASR fallback is attempted automatically

### Backend not running or CORS issues

Symptoms:

- frontend actions fail immediately

Fix:

- confirm backend is running on `http://127.0.0.1:8000`
- confirm `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
- confirm `FRONTEND_ORIGIN=http://localhost:3000`

## Manual Screenshot Placeholder

If you want screenshots in the final submission package, capture:

- home page
- asset detail page
- generator page

They are not required for the app to demo cleanly.
