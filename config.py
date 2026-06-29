"""Configuration for the Stock Advisor engine.

This is the API-only engine behind the Yuktera portal. It has no UI and no
user store — the portal handles login (Supabase) and access control. Tweak the
model, markets, or pick count here.
"""
import os

# --- Claude model -----------------------------------------------------------
# Default model, used when the portal doesn't request a specific one.
CLAUDE_MODEL = "claude-opus-4-8"
MAX_TOKENS = 16000

# Models the portal Admin console is allowed to select. Anything outside this
# set (or missing) falls back to CLAUDE_MODEL — the portal can never make the
# engine run an arbitrary/unintended model.
ALLOWED_MODELS = {"claude-opus-4-8", "claude-sonnet-4-6"}


def resolve_model(requested: str | None) -> str:
    """Return the requested model if it's allowed, else the default."""
    if requested and requested in ALLOWED_MODELS:
        return requested
    return CLAUDE_MODEL

# Number of picks to ask the model for.
NUM_PICKS = 10

# --- Markets ---------------------------------------------------------------
# "suffix" is the Yahoo Finance ticker suffix used by yfinance (e.g.
# RELIANCE.NS for NSE).
MARKETS = {
    "IN_NSE": {"label": "Indian equities (NSE)", "suffix": ".NS", "currency": "INR"},
    "US": {"label": "US equities", "suffix": "", "currency": "USD"},
}
DEFAULT_MARKET = os.getenv("DEFAULT_MARKET", "IN_NSE")


def get_market(key: str) -> dict:
    """Return the market config for a key, falling back to the default."""
    return MARKETS.get(key, MARKETS[DEFAULT_MARKET])


# --- API auth --------------------------------------------------------------
# Shared secret the Yuktera portal must send in the X-Engine-Key header.
# Set this in Render; never commit the real value.
ENGINE_SHARED_SECRET = os.getenv("ENGINE_SHARED_SECRET", "")
