from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests

import config
from agents.llm_client import chat_text
from agents.market_agent import get_market_snapshot, parse_model_json


def _pct_return(history: list[dict[str, Any]], periods: int) -> float:
    if len(history) <= periods:
        return 0.0
    latest = float(history[-1].get("close", 0) or 0)
    prev = float(history[-(periods + 1)].get("close", 0) or 0)
    if prev <= 0:
        return 0.0
    return ((latest - prev) / prev) * 100.0


def _fetch_screener_symbols(scr_id: str, count: int = 25) -> list[str]:
    url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
    params = {"scrIds": scr_id, "count": str(count)}
    resp = requests.get(
        url,
        params=params,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    payload = resp.json()
    results = payload.get("finance", {}).get("result", [])
    if not results:
        return []
    quotes = results[0].get("quotes", [])
    symbols: list[str] = []
    for q in quotes:
        s = str(q.get("symbol", "")).upper().strip()
        if s and s.isascii():
            symbols.append(s)
    return symbols


def _fetch_trending_symbols(count: int = 20) -> list[str]:
    url = "https://query1.finance.yahoo.com/v1/finance/trending/US"
    resp = requests.get(
        url,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    payload = resp.json()
    quotes = payload.get("finance", {}).get("result", [{}])[0].get("quotes", [])
    symbols: list[str] = []
    for q in quotes[:count]:
        s = str(q.get("symbol", "")).upper().strip()
        if s and s.isascii():
            symbols.append(s)
    return symbols


def _build_dynamic_universe() -> tuple[list[str], dict[str, str]]:
    errors: dict[str, str] = {}
    symbols: list[str] = []
    sources = [
        ("day_gainers", "yahoo_day_gainers"),
        ("day_losers", "yahoo_day_losers"),
        ("most_actives", "yahoo_most_actives"),
    ]
    for scr_id, label in sources:
        try:
            symbols.extend(_fetch_screener_symbols(scr_id))
        except Exception as ex:
            errors[label] = str(ex)
    try:
        symbols.extend(_fetch_trending_symbols())
    except Exception as ex:
        errors["yahoo_trending"] = str(ex)

    symbols.extend(config.SCAN_UNIVERSE)

    deduped: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        s = s.upper().strip()
        if not s or s in seen:
            continue
        # Skip non-stock / odd symbols.
        if any(ch in s for ch in ("^", "=", "/", "-", ".")):
            continue
        if len(s) > 5:
            continue
        seen.add(s)
        deduped.append(s)

    return deduped[: config.SCAN_TARGET_UNIVERSE_SIZE], errors


def _build_scan_prompt(rows: list[dict[str, Any]], holdings_context: str) -> str:
    row_lines: list[str] = []
    for r in rows:
        row_lines.append(
            f"- {r['symbol']} | close={r['close']:.2f} | ret5d={r['ret5d']:.2f}% | ret20d={r['ret20d']:.2f}% | head1={r['head1']} | head2={r['head2']}"
        )
    return (
        "You are an equity opportunity scanner. Pick exactly 3 BUY ideas and exactly 3 SHORT ideas for next-session opportunity from the list below.\n"
        "Use only the listed symbols. Avoid weak or low-conviction picks.\n"
        "Account for portfolio construction: prefer improving diversification and avoid over-concentrating positions that are already large unless catalyst conviction is very high.\n\n"
        f"Current holdings context:\n{holdings_context}\n\n"
        "Candidates:\n"
        + "\n".join(row_lines)
        + "\n\nReturn strict JSON with keys buy_ideas and short_ideas.\n"
        "buy_ideas: array of exactly 3 objects.\n"
        "short_ideas: array of exactly 3 objects.\n"
        "Each object keys: symbol, confidence, thesis.\n"
        "thesis must be a concrete catalyst-based justification grounded in the candidate data and headlines.\n"
        "Good thesis examples: merger/acquisition update, earnings surprise, guidance revision, regulatory decision, major product launch, analyst rating change, material contract win/loss.\n"
        "Do not write generic statements like 'strong momentum' or 'mixed headlines' without a specific catalyst.\n"
        "confidence must be integer 0-100."
    )


def _format_holdings_context(holdings: dict[str, Any]) -> str:
    shares = holdings.get("shares", {}) if isinstance(holdings, dict) else {}
    values = holdings.get("values", {}) if isinstance(holdings, dict) else {}
    if not shares:
        return "- No current holdings provided."

    lines: list[str] = []
    for symbol, qty in sorted(shares.items()):
        try:
            q = float(qty)
        except (TypeError, ValueError):
            q = 0.0
        try:
            v = float(values.get(symbol, 0))
        except (TypeError, ValueError):
            v = 0.0
        lines.append(f"- {symbol}: shares={q:.4f}, position_value_usd={v:.2f}")
    return "\n".join(lines)


def run_opportunity_scan(holdings: dict[str, Any] | None = None) -> dict[str, Any]:
    universe, universe_errors = _build_dynamic_universe()
    scan_rows: list[dict[str, Any]] = []
    scan_details: dict[str, Any] = {}
    errors: dict[str, str] = dict(universe_errors)

    for symbol in universe:
        snap = get_market_snapshot(symbol, article_count=config.SCAN_ARTICLE_COUNT)
        history = snap.get("history", [])
        news = snap.get("news", [])
        scan_details[symbol] = {
            "price_source": snap.get("price_source", "none"),
            "news_source": snap.get("news_source", "none"),
            "history_points": len(history),
            "news_count": len(news),
        }
        if snap.get("errors"):
            errors[symbol] = " | ".join(snap["errors"])

        if not history or not news:
            continue
        close = float(history[-1].get("close", 0) or 0)
        if close <= 0:
            continue

        h1 = (news[0].get("title", "") or "").strip()
        h2 = (news[1].get("title", "") or "").strip() if len(news) > 1 else ""
        scan_rows.append(
            {
                "symbol": symbol,
                "close": close,
                "ret5d": _pct_return(history, 5),
                "ret20d": _pct_return(history, 20),
                "head1": h1[:180],
                "head2": h2[:180],
            }
        )

    buy_ideas: list[dict[str, Any]] = []
    short_ideas: list[dict[str, Any]] = []
    row_map = {r["symbol"]: r for r in scan_rows}

    if scan_rows:
        prompt = _build_scan_prompt(scan_rows, _format_holdings_context(holdings or {}))
        try:
            content = chat_text("Return valid JSON only.", prompt, temperature=0.15)
            parsed = parse_model_json(content)
            allowed = set(row_map.keys())

            for rec in parsed.get("buy_ideas", []):
                symbol = str(rec.get("symbol", "")).upper().strip()
                if symbol not in allowed:
                    continue
                row = row_map[symbol]
                thesis = str(rec.get("thesis", "")).strip()
                if len(thesis) < 20:
                    continue
                try:
                    conf = int(rec.get("confidence", 50))
                except (TypeError, ValueError):
                    conf = 50
                conf = max(0, min(conf, 100))
                buy_ideas.append(
                    {
                        "symbol": symbol,
                        "current_price": round(row["close"], 2),
                        "confidence": conf,
                        "ret5d": round(row["ret5d"], 2),
                        "ret20d": round(row["ret20d"], 2),
                        "reason": thesis,
                    }
                )

            for rec in parsed.get("short_ideas", []):
                symbol = str(rec.get("symbol", "")).upper().strip()
                if symbol not in allowed:
                    continue
                row = row_map[symbol]
                thesis = str(rec.get("thesis", "")).strip()
                if len(thesis) < 20:
                    continue
                try:
                    conf = int(rec.get("confidence", 50))
                except (TypeError, ValueError):
                    conf = 50
                conf = max(0, min(conf, 100))
                short_ideas.append(
                    {
                        "symbol": symbol,
                        "current_price": round(row["close"], 2),
                        "confidence": conf,
                        "ret5d": round(row["ret5d"], 2),
                        "ret20d": round(row["ret20d"], 2),
                        "reason": thesis,
                    }
                )
        except Exception as ex:
            errors["scan_ai"] = str(ex)

    buy_ideas = buy_ideas[: config.SCAN_BUY_COUNT]
    short_ideas = short_ideas[: config.SCAN_SHORT_COUNT]
    if len(buy_ideas) < config.SCAN_BUY_COUNT:
        errors["scan_buy_count"] = f"AI returned {len(buy_ideas)} buy ideas; expected {config.SCAN_BUY_COUNT}."
    if len(short_ideas) < config.SCAN_SHORT_COUNT:
        errors["scan_short_count"] = f"AI returned {len(short_ideas)} short ideas; expected {config.SCAN_SHORT_COUNT}."

    generated_at = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": generated_at,
        "model": config.DEFAULT_MODEL,
        "universe_size": len(universe),
        "rows_considered": len(scan_rows),
        "buy_ideas": buy_ideas,
        "short_ideas": short_ideas,
        "errors": errors,
        "scan_details": scan_details,
    }
    with config.OPPORTUNITY_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    return output
