"""Claude-powered stock suggestion engine.

Gives Claude the web_search server tool so it can pull current context from
finance / business / industry sources, then combine that with its own
knowledge to propose a ranked list of stocks tailored to the user's risk
appetite and budget. Returns structured picks (parsed from a JSON block).

This is informational/educational only — NOT financial advice.
"""
import json
import re

import anthropic

import config

_client = None


def _get_client():
    global _client
    if _client is None:
        # Reads ANTHROPIC_API_KEY from the environment.
        _client = anthropic.Anthropic()
    return _client


def _build_prompt(profile: dict) -> str:
    return f"""You are a research assistant helping an individual investor build a
shortlist of stocks to research further. This is educational, not financial advice.

Investor profile:
- Risk appetite: {profile['risk']}
- Investment horizon: {profile['horizon']}
- Amount per month: {profile['monthly']} {profile['currency']}
- Lump sum available now: {profile['lumpsum']} {profile['currency']}
- Market of interest: {profile['market_label']}
- Sectors of interest: {profile['sectors'] or 'no preference'}

Task:
1. Use web search to gather CURRENT context from reputable finance, business,
   industry, manufacturing, and energy sources (recent news, sector trends,
   analyst sentiment). Combine that with your own knowledge.
2. Propose exactly {config.NUM_PICKS} stocks suited to this profile, diversified
   across sectors, and appropriate for the stated risk appetite.
3. Suggest a percentage allocation across the {config.NUM_PICKS} picks that sums
   to 100.

Respond with a short paragraph of overall reasoning, then a fenced JSON code
block (```json ... ```) with EXACTLY this shape:

{{
  "picks": [
    {{
      "ticker": "AAPL",
      "company": "Apple Inc.",
      "sector": "Technology",
      "risk_level": "low|medium|high",
      "allocation_pct": 10,
      "rationale": "1-2 sentences grounded in the research."
    }}
  ],
  "summary": "2-3 sentence overall strategy note."
}}

Use ticker symbols valid on Yahoo Finance for {profile['market_label']}. Allocation
percentages must sum to 100. Output the JSON block exactly once."""


def _extract_text(content) -> str:
    return "".join(block.text for block in content if block.type == "text")


def _parse_picks(text: str) -> dict:
    """Pull the JSON object out of the model's reply."""
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else None
    if raw is None:
        # Fall back to the first balanced-looking object in the text.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        raw = match.group(0) if match else None
    if raw is None:
        raise ValueError("Model response did not contain a JSON block.")
    return json.loads(raw)


def recommend(profile: dict, model: str | None = None) -> dict:
    """Run the research + recommendation loop and return parsed results.

    `model` selects the Claude model (defaults to config.CLAUDE_MODEL).
    Returns a dict: {"picks": [...], "summary": str}.
    """
    client = _get_client()
    model = model or config.CLAUDE_MODEL
    messages = [{"role": "user", "content": _build_prompt(profile)}]
    tools = [{"type": "web_search_20260209", "name": "web_search"}]

    # Server-side web search runs its own loop; it may return pause_turn when it
    # hits the per-turn tool-use limit. Re-send to let it continue.
    for _ in range(6):
        response = client.messages.create(
            model=model,
            max_tokens=config.MAX_TOKENS,
            thinking={"type": "adaptive"},
            tools=tools,
            messages=messages,
        )
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    text = _extract_text(response.content)
    result = _parse_picks(text)
    result.setdefault("summary", "")
    result.setdefault("picks", [])
    return result
