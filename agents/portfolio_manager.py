from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import config


def _score_decision(
    tech: dict[str, Any],
    sent: dict[str, Any],
    weight: float,
    overall_risk_level: str,
) -> tuple[str, float, list[str]]:
    score = 0.0
    notes: list[str] = []

    trend = tech.get("trend", "neutral")
    if trend == "bullish":
        score += 0.8
        notes.append("Trend bullish")
    elif trend == "bearish":
        score -= 0.8
        notes.append("Trend bearish")

    signal = tech.get("technical_signal", "hold")
    if signal == "buy_bias":
        score += 0.8
        notes.append("Technical buy bias")
    elif signal == "sell_bias":
        score -= 0.8
        notes.append("Technical sell bias")

    rsi = tech.get("rsi")
    try:
        rsi = float(rsi)
    except (TypeError, ValueError):
        rsi = None
    if rsi is not None:
        if rsi <= 25:
            score += 1.0
            notes.append("RSI deeply oversold")
        elif rsi <= 35:
            score += 0.5
            notes.append("RSI oversold")
        elif rsi >= 80:
            score -= 1.0
            notes.append("RSI deeply overbought")
        elif rsi >= 70:
            score -= 0.5
            notes.append("RSI overbought")

    macd = tech.get("macd")
    macd_signal = tech.get("macd_signal")
    try:
        macd = float(macd)
        macd_signal = float(macd_signal)
    except (TypeError, ValueError):
        macd = None
        macd_signal = None
    if macd is not None and macd_signal is not None:
        if macd > macd_signal:
            score += 0.4
            notes.append("MACD above signal")
        elif macd < macd_signal:
            score -= 0.4
            notes.append("MACD below signal")

    sentiment = sent.get("sentiment", "neutral")
    sentiment_conf = float(sent.get("confidence", 50)) / 100.0
    if sentiment == "bullish":
        score += 0.9 * sentiment_conf
        notes.append("News sentiment bullish")
    elif sentiment == "bearish":
        score -= 0.9 * sentiment_conf
        notes.append("News sentiment bearish")

    if weight >= 0.4 and score < 0:
        score -= 0.4
        notes.append("Large position with weak signals")

    if overall_risk_level == "high" and score > 0 and weight >= 0.35:
        score -= 0.35
        notes.append("Portfolio risk cap reduces aggressive buys")

    if score >= 1.2:
        decision = "BUY"
    elif score <= -1.2:
        decision = "SELL"
    else:
        decision = "HOLD"

    confidence = min(95.0, max(38.0, 48.0 + abs(score) * 17.0))
    return decision, round(confidence, 1), notes


def _build_report(
    timestamp_iso: str,
    recommendations: dict[str, Any],
    risk: dict[str, Any],
) -> str:
    bullish = [s for s, r in recommendations.items() if r.get("decision") == "BUY"]
    bearish = [s for s, r in recommendations.items() if r.get("decision") == "SELL"]

    lines: list[str] = []
    lines.append(f"# AI Market Report - {timestamp_iso[:10]}")
    lines.append("")
    lines.append("## Bullish Stocks")
    lines.extend([f"- {s}" for s in bullish] or ["- None"])
    lines.append("")
    lines.append("## Bearish Stocks")
    lines.extend([f"- {s}" for s in bearish] or ["- None"])
    lines.append("")
    lines.append("## Portfolio Recommendations")
    for symbol, rec in recommendations.items():
        lines.append(
            f"- {symbol}: {rec['decision']} "
            f"(confidence {rec['confidence']}%) - {rec['summary']}"
        )
    lines.append("")
    lines.append(f"Overall Portfolio Risk: {risk.get('risk_level', 'unknown')}")
    lines.append(f"Risk Score: {risk.get('risk_score', 'n/a')}/100")
    flags = risk.get("risk_flags", [])
    if flags:
        lines.append("")
        lines.append("Risk Flags:")
        lines.extend([f"- {f}" for f in flags])

    return "\n".join(lines) + "\n"


def run_portfolio_manager() -> dict[str, Any]:
    with config.STOCK_DATA_FILE.open("r", encoding="utf-8") as f:
        stock_data = json.load(f)
    with config.TECHNICAL_FILE.open("r", encoding="utf-8") as f:
        technical = json.load(f)
    with config.SENTIMENT_FILE.open("r", encoding="utf-8") as f:
        sentiment = json.load(f)
    with config.RISK_FILE.open("r", encoding="utf-8") as f:
        risk = json.load(f)

    portfolio_shares: dict[str, float] = stock_data.get("portfolio_shares", stock_data.get("portfolio", {}))
    portfolio_values: dict[str, float] = stock_data.get("portfolio_values", {})
    stocks: dict[str, Any] = stock_data.get("stocks", {})
    if not portfolio_values:
        for symbol, shares in portfolio_shares.items():
            history = stocks.get(symbol, {}).get("history", [])
            if history:
                last_close = float(history[-1].get("close", 0) or 0)
                if last_close > 0:
                    portfolio_values[symbol] = shares * last_close

    total_value = sum(portfolio_values.values()) or 1.0
    tech_map: dict[str, Any] = technical.get("analysis", {})
    sent_map: dict[str, Any] = sentiment.get("analysis", {})
    overall_risk_level = risk.get("risk_level", "unknown")

    recommendations: dict[str, Any] = {}
    for symbol in portfolio_shares:
        position_value = portfolio_values.get(symbol, 0.0)
        weight = position_value / total_value if position_value > 0 else 0.0
        tech = tech_map.get(symbol, {})
        sent = sent_map.get(symbol, {})
        decision, confidence, notes = _score_decision(tech, sent, weight, overall_risk_level)

        recommendations[symbol] = {
            "decision": decision,
            "confidence": confidence,
            "summary": "; ".join(notes) if notes else "Limited signal, keep watch.",
            "position_weight": round(weight, 4),
            "position_value": round(position_value, 2),
        }

    generated_at = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": generated_at,
        "recommendations": recommendations,
        "overall_risk_level": risk.get("risk_level", "unknown"),
        "overall_risk_score": risk.get("risk_score", 0),
    }

    with config.RECOMMENDATION_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    report = _build_report(generated_at, recommendations, risk)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with config.DAILY_REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write(report)

    return output
