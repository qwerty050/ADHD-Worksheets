# ADHD Worksheets: Web App

The browser front end for ADHD Worksheets (React 19, TypeScript, Vite). With it you can create or upload a Course Memory knowledge base (`.cmkb`), add question JSON files and reference PDFs, upload a lecture (as a PDF, or as pedagogical JSON pasted from a chatbot), generate the worksheet with live progress, and then download the `.tex` worksheet and the updated KB. It also has a Config page for the backend `.env` and an AI Guide with copy-paste chatbot prompts.

It is only a UI. Every bit of work (extraction, generation, memory) happens in the FastAPI backend (`api/server.py`).

## Run it

Requires Node.js `^20.19` or `>=22.12`.

1. Start the backend from the repo root (see the [main README](../README.md) for the Python and Ollama setup):
   ```bash
   uvicorn api.server:app --reload --port 8000
   ```
2. Start the dev server:
   ```bash
   cd web
   npm install
   npm run dev
   ```
3. Open `http://localhost:5173`.

Other scripts: `npm run build` (type-check with `tsc -b`, then build to `dist/`), `npm run preview` (serve the build), `npm run lint` (oxlint).

## How it talks to the API

`src/api.ts` is the single API client. Every request goes to `API_BASE`, which is `VITE_API_URL` or, if that is not set, `http://localhost:8000/api`. Generation progress is read from a Server-Sent Events stream (`GET /sessions/{id}/generate`). The routes are listed in [docs/usage.md](../docs/usage.md#http-api).

To point the UI at another backend, create `web/.env.local`:

```env
VITE_API_URL=http://my-host:8000/api
```

The value must include the `/api` suffix. Vite reads it at dev-server start and at build time, so restart `npm run dev` (or rebuild) after you change it. The backend allows CORS from any origin.

The backend keeps each browser session's KB and lecture in a temporary folder, and memory updates go to that copy. Download the KB at the end if you want to keep them. Sessions are lost when the backend restarts.
