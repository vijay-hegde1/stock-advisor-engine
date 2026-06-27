# Yuktera — Stock Advisor Engine

A small Python (FastAPI) API that powers the **Stock Advisor** tool in the
Yuktera portal. It has **no UI and no login** — the portal handles the screen
(Next.js), authentication (Supabase), and access control. This service only does
the work: ask Claude for a stock shortlist (with web search), then enrich each
pick with a live price from Yahoo Finance.

> Educational only — **not financial advice.**

## How it fits in

```
Portal page (Next.js, Yuktera-styled, Supabase-gated)
   → portal server route  (checks session + tool_access entitlement)
        → POST /recommend here  (X-Engine-Key shared secret)
             → Claude (web search) + yfinance
        ← JSON { picks, summary, profile }
   → rendered in the portal
```

The browser never calls this service directly.

## API

`POST /recommend` — header `X-Engine-Key: <ENGINE_SHARED_SECRET>`

```json
{
  "risk": "medium",
  "horizon": "3-5 years",
  "monthly": "10000",
  "lumpsum": "100000",
  "market": "IN_NSE",
  "sectors": "tech, energy"
}
```

Returns `{ "picks": [...], "summary": "...", "profile": {...} }`. Each pick has a
`live` object with the current price from yfinance.

`GET /health` — returns `{"status": "ok"}` (used by Render's health check).

## Environment variables

| Var | What |
|-----|------|
| `ANTHROPIC_API_KEY` | Anthropic key (the advisor calls Claude) |
| `ENGINE_SHARED_SECRET` | Long random string; the portal must send the same value in `X-Engine-Key` |
| `DEFAULT_MARKET` | `IN_NSE` or `US` (optional, default `IN_NSE`) |

Copy `.env.example` → `.env` for local dev. On Render, set them in the service's
Environment settings.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env           # then fill in the values
uvicorn app:app --reload --port 8000
# test:  http://127.0.0.1:8000/health
```

## Deploy to Render

1. Push this folder to a GitHub repo (e.g. `vijay-hegde1/stock-advisor-engine`).
2. Render → **New → Blueprint** → select the repo (`render.yaml` is detected), or
   **New → Web Service** with:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/health`
3. Set environment variables `ANTHROPIC_API_KEY` and `ENGINE_SHARED_SECRET`
   (and optionally `DEFAULT_MARKET`).
4. Deploy. Note the service URL (e.g. `https://stock-advisor-engine.onrender.com`)
   — the portal needs it as `STOCK_ADVISOR_ENGINE_URL`.

> Note: Render's free tier sleeps after inactivity, so the first request after a
> while is slow to wake. Fine for demos; upgrade the plan for always-on.
