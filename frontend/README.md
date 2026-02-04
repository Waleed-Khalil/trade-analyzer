# Trade Analyzer — Frontend

Next.js 14 app for the option play analyzer. Paste a play, get Go/No-Go, Greeks, risk, and recommendation in a single dashboard.

## Setup

```bash
npm install
cp .env.local.example .env.local   # optional: set NEXT_PUBLIC_API_URL if backend is not on :8000
```

## Run

1. **Start the backend** (from repo root):

   ```bash
   python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000
   ```

   If port 8000 is already in use, run with `--port 8001` (or another port) and set `NEXT_PUBLIC_API_URL=http://localhost:8001` in `.env.local`.

2. **Start the frontend**:

   ```bash
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000). Paste an option play (e.g. `MSFT 430 CALL @ 0.79 EXP 2026-02-06`) and click **Analyze**.

## Env

- `NEXT_PUBLIC_API_URL` — Backend API base URL (default: `http://localhost:8000`).
