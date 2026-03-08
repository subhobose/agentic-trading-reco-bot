from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    out: dict[str, float] = {}
    for symbol, qty in raw.items():
        try:
            q = float(qty)
        except (TypeError, ValueError):
            continue
        if q > 0:
            out[str(symbol).upper()] = q
    return out


def _try_robinhood() -> tuple[dict[str, float], dict[str, float]]:
    if not config.USE_ROBINHOOD or rh is None:
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
    shares: dict[str, float] = {}
    values: dict[str, float] = {}
    for symbol, payload in holdings.items():
        try:
            qty = float(payload.get("quantity", 0))
        except (TypeError, ValueError):
            qty = 0.0
        try:
            val = float(payload.get("equity", 0))
        except (TypeError, ValueError):
            val = 0.0
        if qty > 0:
            s = symbol.upper()
            shares[s] = qty
            if val > 0:
                values[s] = val
    rh.logout()
    return shares, values


def get_holdings() -> dict[str, Any]:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    shares, values = {}, {}
    source = "portfolio.json"
    try:
        shares, values = _try_robinhood()
    except Exception as ex:  # pragma: no cover
        print(f"[holdings_agent] Robinhood failed: {ex}")

    if shares:
        with config.PORTFOLIO_FILE.open("w", encoding="utf-8") as f:
            json.dump(shares, f, indent=2)
        source = "robinhood"
    else:
        shares = _read_portfolio_file(config.PORTFOLIO_FILE)

    return {
        "source": source,
        "shares": shares,
        "values": values,
        "tickers": sorted(shares.keys()),
    }

