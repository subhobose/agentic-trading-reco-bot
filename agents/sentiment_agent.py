from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import ollama

import config


def _build_prompt(symbol: str, company: str, headlines: list[str]) -> str:
    list_block = "\n".join(f"- {h}" for h in headlines if h.strip())
    return (
        f"You are a financial news sentiment analyst.\n"
        f"Ticker: {symbol}\n"
        f"Company: {company}\n"
        f"Recent headlines:\n{list_block}\n\n"
        "Respond strictly as JSON with keys: summary, sentiment, confidence.\n"
        "sentiment must be one of: bullish, neutral, bearish.\n"
        "confidence must be an integer 0-100."
    )


def _fallback_sentiment(headlines: list[str]) -> dict[str, Any]:
    text = " ".join(headlines).lower()
    positive = sum(w in text for w in ("beats", "upgrade", "growth", "surge", "record", "gain"))
    negative = sum(w in text for w in ("miss", "downgrade", "lawsuit", "drop", "decline", "fall"))
    if positive > negative:
        return {"summary": "Mostly positive headlines.", "sentiment": "bullish", "confidence": 58}
    if negative > positive:
        return {"summary": "Mostly negative headlines.", "sentiment": "bearish", "confidence": 58}
    return {"summary": "Mixed or limited signal in headlines.", "sentiment": "neutral", "confidence": 50}


def _query_ollama(prompt: str) -> dict[str, Any]:
    kwargs = {}
    if config.OLLAMA_HOST:
        kwargs["host"] = config.OLLAMA_HOST
    client = ollama.Client(**kwargs) if kwargs else ollama

    resp = client.chat(
        model=config.DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": "Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": 0.1},
    )
    content = resp["message"]["content"]
    parsed = json.loads(content)

    sentiment = str(parsed.get("sentiment", "neutral")).lower().strip()
    if sentiment not in {"bullish", "neutral", "bearish"}:
        sentiment = "neutral"

    confidence = parsed.get("confidence", 50)
    try:
        confidence = int(confidence)
    except (TypeError, ValueError):
        confidence = 50
    confidence = max(0, min(confidence, 100))

    return {
        "summary": str(parsed.get("summary", "")).strip() or "No summary returned.",
        "sentiment": sentiment,
        "confidence": confidence,
    }


def run_sentiment_analysis() -> dict[str, Any]:
    with config.STOCK_DATA_FILE.open("r", encoding="utf-8") as f:
        stock_data = json.load(f)

    results: dict[str, Any] = {}
    for symbol, payload in stock_data.get("stocks", {}).items():
        company = payload.get("company", symbol)
        news = payload.get("news", [])
        headlines = [item.get("title", "").strip() for item in news if item.get("title")]
        if not headlines:
            results[symbol] = {
                "summary": "No recent headlines found.",
                "sentiment": "neutral",
                "confidence": 40,
                "source": "fallback_no_news",
            }
            continue

        prompt = _build_prompt(symbol, company, headlines)
        try:
            analyzed = _query_ollama(prompt)
            analyzed["source"] = "ollama"
            results[symbol] = analyzed
        except Exception:
            analyzed = _fallback_sentiment(headlines)
            analyzed["source"] = "fallback_heuristic"
            results[symbol] = analyzed

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": config.DEFAULT_MODEL,
        "analysis": results,
    }

    with config.SENTIMENT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output

