"""Live market data via yfinance.

Used to enrich the model's picks with real, current numbers so the user
isn't relying on the LLM for prices (which it can get wrong or stale).
"""
import yfinance as yf


def _full_ticker(symbol: str, suffix: str) -> str:
    symbol = symbol.strip().upper()
    # Don't double-append a suffix if the model already included one.
    if suffix and not symbol.endswith(suffix):
        return symbol + suffix
    return symbol


def quote(symbol: str, suffix: str = "") -> dict:
    """Fetch a current snapshot for one ticker. Always returns a dict;
    fields are None when lookup fails so the UI can degrade gracefully."""
    ticker = _full_ticker(symbol, suffix)
    snapshot = {
        "symbol": ticker,
        "price": None,
        "currency": None,
        "name": None,
        "sector": None,
        "market_cap": None,
        "pe_ratio": None,
        "error": None,
    }
    try:
        info = yf.Ticker(ticker).info or {}
        snapshot["price"] = info.get("currentPrice") or info.get("regularMarketPrice")
        snapshot["currency"] = info.get("currency")
        snapshot["name"] = info.get("shortName") or info.get("longName")
        snapshot["sector"] = info.get("sector")
        snapshot["market_cap"] = info.get("marketCap")
        snapshot["pe_ratio"] = info.get("trailingPE")
    except Exception as exc:  # network/ticker errors shouldn't crash the response
        snapshot["error"] = str(exc)
    return snapshot


def enrich(picks: list, suffix: str = "") -> list:
    """Attach a live quote to each pick dict (in place) and return the list."""
    for pick in picks:
        pick["live"] = quote(pick.get("ticker", ""), suffix)
    return picks
