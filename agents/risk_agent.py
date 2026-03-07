from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import config


def _position_weights(position_values: dict[str, float]) -> dict[str, float]:
    total = sum(position_values.values())
    if total <= 0:
        return {}
    return {s: v / total for s, v in position_values.items()}


def run_risk_analysis() -> dict[str, Any]:
    with config.STOCK_DATA_FILE.open("r", encoding="utf-8") as f:
        stock_data = json.load(f)
    with config.TECHNICAL_FILE.open("r", encoding="utf-8") as f:
        technical = json.load(f)

    portfolio_shares: dict[str, float] = stock_data.get("portfolio_shares", stock_data.get("portfolio", {}))
    portfolio_values: dict[str, float] = stock_data.get("portfolio_values", {})
    stocks: dict[str, Any] = stock_data.get("stocks", {})
    tech_map: dict[str, Any] = technical.get("analysis", {})

    if not portfolio_values:
        # Fallback: estimate value from latest close if explicit values are missing.
        for symbol, shares in portfolio_shares.items():
            history = stocks.get(symbol, {}).get("history", [])
            if not history:
                continue
            last_close = float(history[-1].get("close", 0) or 0)
            if last_close > 0:
                portfolio_values[symbol] = shares * last_close

    weights = _position_weights(portfolio_values)

    sector_weights: dict[str, float] = {}
    for symbol, w in weights.items():
        sector = stocks.get(symbol, {}).get("sector", "Unknown")
        sector_weights[sector] = sector_weights.get(sector, 0.0) + w

    positions_count = len(weights) or 1
    sector_threshold = 0.65 if positions_count <= 3 else 0.5
    overweight_threshold = 0.55 if positions_count <= 3 else 0.3

    high_sector = {k: round(v, 4) for k, v in sector_weights.items() if v >= sector_threshold}
    overweight_positions = {s: round(w, 4) for s, w in weights.items() if w >= overweight_threshold}

    high_vol_symbols: list[str] = []
    for symbol in weights:
        vol_class = tech_map.get(symbol, {}).get("volatility_class")
        if vol_class == "high":
            high_vol_symbols.append(symbol)

    max_sector_weight = max(sector_weights.values()) if sector_weights else 0.0
    sector_excess = max(0.0, max_sector_weight - sector_threshold)
    sector_component = min(40.0, sector_excess * 120.0)

    overweight_component = min(35.0, (len(overweight_positions) / positions_count) * 35.0)
    high_vol_component = min(25.0, (len(high_vol_symbols) / positions_count) * 25.0)

    risk_score = int(round(sector_component + overweight_component + high_vol_component))
    risk_flags: list[str] = []
    if high_sector:
        risk_flags.append("High sector concentration.")
    if overweight_positions:
        risk_flags.append("One or more overweight positions.")
    if high_vol_symbols:
        risk_flags.append("High volatility exposure.")
    risk_score = min(risk_score, 100)

    level = "low"
    if risk_score >= 65:
        level = "high"
    elif risk_score >= 35:
        level = "moderate"

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "position_weights": {k: round(v, 4) for k, v in weights.items()},
        "portfolio_values": {k: round(v, 2) for k, v in portfolio_values.items()},
        "sector_weights": {k: round(v, 4) for k, v in sector_weights.items()},
        "sector_threshold": sector_threshold,
        "overweight_threshold": overweight_threshold,
        "high_sector_concentration": high_sector,
        "overweight_positions": overweight_positions,
        "high_volatility_symbols": high_vol_symbols,
        "risk_level": level,
        "risk_score": risk_score,
        "risk_flags": risk_flags,
    }

    with config.RISK_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output
