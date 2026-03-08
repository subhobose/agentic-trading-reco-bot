from __future__ import annotations

from datetime import datetime

import config
from agents.holdings_agent import get_holdings
from agents.market_agent import run_market_agent
from agents.opportunity_agent import run_opportunity_scan


def _build_simple_report(market_payload: dict, opportunity_payload: dict) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines: list[str] = [f"# Simple Agent Report - {date_str}", ""]

    stocks = market_payload.get("stocks", {})
    holdings = market_payload.get("holdings", {})
    errors = market_payload.get("errors", {})
    if not stocks:
        lines.append("No stock analysis generated.")
        return "\n".join(lines) + "\n"

    for symbol, payload in stocks.items():
        ai = payload.get("ai_view", {})
        if not ai:
            raw_error = errors.get(symbol, "No AI output returned and no explicit error was captured.")
            lines.append(f"## {symbol}")
            lines.append("- Action: N/A")
            lines.append("- Sentiment: N/A")
            lines.append("- Confidence: N/A")
            lines.append("- 1D Price Change: N/A")
            lines.append(f"- Error: {raw_error}")
            lines.append("")
            continue
        lines.append(f"## {symbol}")
        lines.append(f"- Action: {str(ai.get('action_bias', 'hold')).upper()}")
        lines.append(f"- Sentiment: {str(ai.get('sentiment', 'neutral')).upper()}")
        lines.append(f"- Confidence: {ai.get('confidence', 0)}%")
        lines.append(f"- Current Price: ${ai.get('current_price', payload.get('current_price', 0) or 0)}")
        lines.append(f"- Shares Held: {holdings.get(symbol, {}).get('shares', 0)}")
        lines.append(f"- Position Value: ${holdings.get(symbol, {}).get('position_value', 0)}")
        lines.append(f"- 1D Price Change: {ai.get('price_change_1d_pct', 0)}%")
        lines.append(f"- Reason: {ai.get('summary', 'No summary')}")
        lines.append(f"- Portfolio Plan: {str(ai.get('portfolio_action_plan', 'hold')).upper()}")
        lines.append(f"- Portfolio Justification: {ai.get('portfolio_justification', 'No portfolio justification')}")
        lines.append("")

    lines.append("## New Buy Opportunities (Top 3)")
    buy_recs = opportunity_payload.get("buy_ideas", [])
    if buy_recs:
        for rec in buy_recs:
            lines.append(
                f"- {rec.get('symbol', '')}: BUY @ ${rec.get('current_price', 0)} "
                f"(confidence {rec.get('confidence', 0)}%) - {rec.get('reason', '')}"
            )
    else:
        lines.append("- No buy opportunities produced this run.")

    lines.append("")
    lines.append("## New Short Opportunities (Top 3)")
    short_recs = opportunity_payload.get("short_ideas", [])
    if short_recs:
        for rec in short_recs:
            lines.append(
                f"- {rec.get('symbol', '')}: SHORT @ ${rec.get('current_price', 0)} "
                f"(confidence {rec.get('confidence', 0)}%) - {rec.get('reason', '')}"
            )
    else:
        lines.append("- No short opportunities produced this run.")
    opp_errors = opportunity_payload.get("errors", {})
    if opp_errors:
        lines.append("")
        lines.append("Opportunity Scan Errors:")
        for key, msg in opp_errors.items():
            lines.append(f"- {key}: {msg}")
    lines.append("")

    return "\n".join(lines)


def run() -> None:
    print("[1/4] Getting holdings...")
    holdings = get_holdings()

    print("[2/4] Running market AI scraping agent...")
    market_payload = run_market_agent(holdings)

    print("[3/4] Running opportunity scan agent...")
    enriched_holdings = {
        "shares": holdings.get("shares", {}),
        "values": {k: v.get("position_value", 0) for k, v in market_payload.get("holdings", {}).items()},
    }
    opportunity_payload = run_opportunity_scan(enriched_holdings)

    print("[4/4] Writing report...")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_text = _build_simple_report(market_payload, opportunity_payload)
    with config.DAILY_REPORT_FILE.open("w", encoding="utf-8") as f:
        f.write(report_text)

    print("[done] Report:", config.DAILY_REPORT_FILE)
    print("[done] Agent market payload:", config.DATA_DIR / "agent_market_view.json")
    print("[done] Opportunity payload:", config.OPPORTUNITY_FILE)


if __name__ == "__main__":
    run()
