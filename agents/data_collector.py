from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

import config

try:
    import robin_stocks.robinhood as rh
except Exception:  # pragma: no cover
    rh = None


def _read_portfolio_file(path: Path) -> dict[str, float]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return {str(k).upper(): float(v) for k, v in raw.items() if float(v) > 0}


def _write_portfolio_file(path: Path, portfolio: dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2)


def _try_robinhood_holdings() -> tuple[dict[str, float], dict[str, float]]:
    if not config.USE_ROBINHOOD:
        return {}, {}
    if rh is None:
        return {}, {}
    if not (config.RH_USERNAME and config.RH_PASSWORD):
        return {}, {}

    login = rh.login(
        username=config.RH_USERNAME,
        password=config.RH_PASSWORD,
        mfa_code=config.RH_MFA_CODE or None,
        store_session=True,
    )
    if not login:
        return {}, {}

    holdings = rh.account.build_holdings()
    parsed_shares: dict[str, float] = {}
    parsed_values: dict[str, float] = {}
    for symbol, payload in holdings.items():
        qty = payload.get("quantity")
        if qty is None:
            continue
        try:
            qty_f = float(qty)
        except (TypeError, ValueError):
            continue
        if qty_f > 0:
            symbol_u = symbol.upper()
            parsed_shares[symbol_u] = qty_f
            equity_f = _safe_float(payload.get("equity"))
            if equity_f > 0:
                parsed_values[symbol_u] = equity_f

    rh.logout()
    return parsed_shares, parsed_values


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compact_history_df_to_records(hist_df: Any) -> list[dict[str, Any]]:
    if hist_df is None or hist_df.empty:
        return []
    records: list[dict[str, Any]] = []
    for idx, row in hist_df.iterrows():
        records.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": _safe_float(row.get("Open")),
                "high": _safe_float(row.get("High")),
                "low": _safe_float(row.get("Low")),
                "close": _safe_float(row.get("Close")),
                "volume": _safe_float(row.get("Volume")),
            }
        )
    return records


def _collect_for_ticker(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}

    history = ticker.history(period=config.HISTORY_PERIOD, interval=config.HISTORY_INTERVAL)
    history_records = _compact_history_df_to_records(history)

    news_payload = ticker.news or []
    news_items: list[dict[str, Any]] = []
    for item in news_payload[: config.NEWS_PER_TICKER]:
        content = item.get("content", {})
        news_items.append(
            {
                "title": content.get("title") or item.get("title", ""),
                "summary": content.get("summary") or "",
                "publisher": content.get("provider", {}).get("displayName") or item.get("publisher", ""),
                "published_at": content.get("pubDate") or item.get("providerPublishTime"),
                "url": content.get("canonicalUrl", {}).get("url") or item.get("link", ""),
            }
        )

    return {
        "symbol": symbol,
        "company": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector") or "Unknown",
        "industry": info.get("industry") or "Unknown",
        "market_cap": _safe_float(info.get("marketCap")),
        "beta": _safe_float(info.get("beta"), default=1.0),
        "trailing_pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "average_volume": _safe_float(info.get("averageVolume")),
        "history": history_records,
        "news": news_items,
    }


def collect_market_data() -> dict[str, Any]:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    robinhood_portfolio_shares: dict[str, float] = {}
    robinhood_portfolio_values: dict[str, float] = {}
    try:
        robinhood_portfolio_shares, robinhood_portfolio_values = _try_robinhood_holdings()
    except Exception as ex:  # pragma: no cover
        print(f"[data_collector] Robinhood fetch failed: {ex}")

    file_portfolio_shares = _read_portfolio_file(config.PORTFOLIO_FILE)

    if robinhood_portfolio_shares:
        portfolio_shares = robinhood_portfolio_shares
        portfolio_values = robinhood_portfolio_values
        _write_portfolio_file(config.PORTFOLIO_FILE, robinhood_portfolio_shares)
        portfolio_source = "robinhood"
    else:
        portfolio_shares = file_portfolio_shares
        portfolio_values = {}
        portfolio_source = "portfolio.json"

    tickers = sorted(portfolio_shares.keys())
    stocks: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for symbol in tickers:
        try:
            stocks[symbol] = _collect_for_ticker(symbol)
        except Exception as ex:  # pragma: no cover
            errors[symbol] = str(ex)

    # Fill missing portfolio values from latest close * shares when possible.
    for symbol, shares in portfolio_shares.items():
        if portfolio_values.get(symbol, 0) > 0:
            continue
        history = stocks.get(symbol, {}).get("history", [])
        if not history:
            continue
        last_close = _safe_float(history[-1].get("close"))
        if last_close > 0:
            portfolio_values[symbol] = round(last_close * shares, 4)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portfolio_source": portfolio_source,
        "portfolio": portfolio_shares,  # Backward compatibility for previous readers.
        "portfolio_shares": portfolio_shares,
        "portfolio_values": portfolio_values,
        "tickers": tickers,
        "stocks": stocks,
        "errors": errors,
    }

    with config.STOCK_DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload
