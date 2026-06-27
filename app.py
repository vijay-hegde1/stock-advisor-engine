"""Stock Advisor engine — a small JSON API.

The Yuktera portal calls POST /recommend server-to-server (never the browser).
Auth is a shared secret in the X-Engine-Key header — combined with the portal's
own Supabase session + entitlement checks, this keeps the public Render URL
from being used by anyone but the portal.

Anthropic + market data run here; the portal only renders the result.
"""
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

import config
from services import advisor, market

load_dotenv()

app = FastAPI(title="Yuktera Stock Advisor Engine")


class Profile(BaseModel):
    risk: str = "medium"
    horizon: str = "3-5 years"
    monthly: str = "0"
    lumpsum: str = "0"
    market: str = config.DEFAULT_MARKET
    sectors: str = ""


def _check_secret(x_engine_key: Optional[str]) -> None:
    expected = config.ENGINE_SHARED_SECRET
    if not expected or x_engine_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/recommend")
def recommend(profile: Profile, x_engine_key: Optional[str] = Header(default=None)) -> dict:
    _check_secret(x_engine_key)

    chosen = config.get_market(profile.market)
    enriched_profile = {
        "risk": profile.risk,
        "horizon": profile.horizon,
        "monthly": profile.monthly,
        "lumpsum": profile.lumpsum,
        "currency": chosen["currency"],
        "market_label": chosen["label"],
        "sectors": profile.sectors.strip(),
    }

    try:
        result = advisor.recommend(enriched_profile)
        picks = market.enrich(result.get("picks", []), chosen["suffix"])
    except Exception as exc:  # surface a clean error to the portal
        raise HTTPException(status_code=502, detail=f"Engine error: {exc}")

    return {
        "picks": picks,
        "summary": result.get("summary", ""),
        "profile": enriched_profile,
    }
