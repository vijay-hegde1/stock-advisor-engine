"""Claude-powered stock suggestion engine.

Gives Claude the web_search server tool so it can pull current context from
finance / business / industry sources, then combine that with its own
knowledge to propose a ranked list of stocks tailored to the user's risk
appetite and budget. Returns structured picks (parsed from a JSON block).

This is informational/educational only — NOT financial advice.
"""
import json
import logging
import re

import anthropic

import config

logger = logging.getLogger(__name__)

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


def _iter_balanced_json(text: str):
    """Yield every brace-balanced {...} span in text, left to right."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            depth = 0
            for j in range(i, n):
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        yield text[i : j + 1]
                        i = j
                        break
            else:
                break
        i += 1


def _parse_picks(text: str) -> dict:
    """Pull the JSON object out of the model's reply.

    The model isn't always consistent about emitting exactly one fenced JSON
    block — it may add commentary, a schema example, or multiple candidate
    blocks before the real answer. Collect every fenced ```json block and
    every brace-balanced {...} span (not a greedy regex, which can span from
    the first `{` to the last `}` in the whole response and grab unrelated
    prose), then prefer the LAST one that parses with a "picks" key — the
    model's final answer comes after any preamble or scratch work.
    """
    candidates = [m.group(1).strip() for m in re.finditer(r"```json\s*(.*?)```", text, re.DOTALL)]
    candidates.extend(_iter_balanced_json(text))

    for raw in reversed(candidates):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "picks" in parsed:
            return parsed

    logger.error(
        "Stock Advisor: no parseable JSON 'picks' block in model response. "
        "First 1000 chars: %r",
        text[:1000],
    )
    raise ValueError("Model response did not contain a parseable JSON block.")


def recommend(profile: dict, model: str | None = None) -> dict:
    """Run the research + recommendation loop and return parsed results.

    `model` selects the Claude model (defaults to config.CLAUDE_MODEL).
    Returns a dict: {"picks": [...], "summary": str}.
    """
    client = _get_client()
    model = model or config.CLAUDE_MODEL
    messages = [{"role": "user", "content": _build_prompt(profile)}]
    # Cap web search so the server-side research loop stays bounded — keeps the
    # call within the portal's request timeout and controls cost.
    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": config.WEB_SEARCH_MAX_USES,
        }
    ]

    # Server-side web search runs its own loop; it may return pause_turn when it
    # hits the per-turn tool-use limit. Re-send to let it continue.
    for _ in range(6):
        response = client.messages.create(
            model=model,
            max_tokens=config.MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": config.EFFORT},
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
