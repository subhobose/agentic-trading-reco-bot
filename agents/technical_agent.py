from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD

import config


def _to_frame(history: list[dict[str, Any]]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"])


def _classify_volatility(vol: float) -> str:
    if vol < 0.01:
        return "low"
    if vol < 0.025:
        return "medium"
    return "high"


def _analyze_symbol(symbol: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    df = _to_frame(history)
    if df.empty or len(df) < 35:
        return {
            "symbol": symbol,
            "status": "insufficient_data",
        }

    close = df["close"]

    rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
    ema_12 = close.ewm(span=12, adjust=False).mean().iloc[-1]
    ema_26 = close.ewm(span=26, adjust=False).mean().iloc[-1]
    sma_20 = close.rolling(window=20).mean().iloc[-1]
    sma_50 = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else None

    macd_obj = MACD(close=close)
    macd = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]

    returns = close.pct_change().dropna()
    annualized_vol = returns.std() * (252**0.5) if not returns.empty else 0.0

    trend = "neutral"
    if sma_50 is not None:
        if sma_20 > sma_50 and close.iloc[-1] > sma_20:
            trend = "bullish"
        elif sma_20 < sma_50 and close.iloc[-1] < sma_20:
            trend = "bearish"

    signal = "hold"
    if rsi < 35 and macd > macd_signal and trend != "bearish":
        signal = "buy_bias"
    elif rsi > 70 and macd < macd_signal and trend != "bullish":
        signal = "sell_bias"

    return {
        "symbol": symbol,
        "status": "ok",
        "rsi": round(float(rsi), 2),
        "ema_12": round(float(ema_12), 2),
        "ema_26": round(float(ema_26), 2),
        "sma_20": round(float(sma_20), 2),
        "sma_50": round(float(sma_50), 2) if sma_50 is not None else None,
        "macd": round(float(macd), 4),
        "macd_signal": round(float(macd_signal), 4),
        "volatility": round(float(annualized_vol), 4),
        "volatility_class": _classify_volatility(float(annualized_vol)),
        "trend": trend,
        "technical_signal": signal,
    }


def run_technical_analysis() -> dict[str, Any]:
    with config.STOCK_DATA_FILE.open("r", encoding="utf-8") as f:
        stock_data = json.load(f)

    results: dict[str, Any] = {}
    for symbol, payload in stock_data.get("stocks", {}).items():
        results[symbol] = _analyze_symbol(symbol, payload.get("history", []))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis": results,
    }
    with config.TECHNICAL_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    return output

