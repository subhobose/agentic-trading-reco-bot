from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

import config
from agents.llm_client import chat_text


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _stooq_symbol(symbol: str) -> str:
    return f"{symbol.lower()}{config.DEFAULT_MARKET_SUFFIX.lower()}"


def _to_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "date": row.get("Date", "") or row.get("date", ""),
                "open": _safe_float(row.get("Open", row.get("open"))),
                "high": _safe_float(row.get("High", row.get("high"))),
                "low": _safe_float(row.get("Low", row.get("low"))),
                "close": _safe_float(row.get("Close", row.get("close"))),
                "volume": _safe_float(row.get("Volume", row.get("volume"))),
            }
        )
    return out[-120:]


def _fetch_price_history_stooq(symbol: str) -> list[dict[str, Any]]:
    url = f"https://stooq.com/q/d/l/?s={_stooq_symbol(symbol)}&i=d"
    resp = requests.get(
        url,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    return _to_rows(rows)


def _fetch_price_history_yahoo(symbol: str) -> list[dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d"
    resp = requests.get(
        url,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("chart", {}).get("result")
    if not result:
        return []
    block = result[0]
    timestamps = block.get("timestamp", []) or []
    quote_block = (block.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote_block.get("open", []) or []
    highs = quote_block.get("high", []) or []
    lows = quote_block.get("low", []) or []
    closes = quote_block.get("close", []) or []
    volumes = quote_block.get("volume", []) or []
    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        rows.append(
            {
                "date": dt,
                "open": _safe_float(opens[i] if i < len(opens) else None),
                "high": _safe_float(highs[i] if i < len(highs) else None),
                "low": _safe_float(lows[i] if i < len(lows) else None),
                "close": _safe_float(closes[i] if i < len(closes) else None),
                "volume": _safe_float(volumes[i] if i < len(volumes) else None),
            }
        )
    return rows[-120:]


def _fetch_price_history(symbol: str) -> tuple[list[dict[str, Any]], str, list[str]]:
    errors: list[str] = []
    try:
        rows = _fetch_price_history_yahoo(symbol)
        if rows:
            return rows, "yahoo_chart_api", errors
        errors.append("yahoo_chart_api: empty response")
    except Exception as ex:
        errors.append(f"yahoo_chart_api: {ex}")

    try:
        rows = _fetch_price_history_stooq(symbol)
        if rows:
            return rows, "stooq_csv", errors
        errors.append("stooq_csv: empty response")
    except Exception as ex:
        errors.append(f"stooq_csv: {ex}")

    return [], "none", errors


def _parse_rss_items(xml_bytes: bytes) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    out: list[dict[str, str]] = []
    items = root.findall("./channel/item")[: config.SCRAPE_NEWS_COUNT]
    for item in items:
        link = item.findtext("link", default="").strip()
        source = item.findtext("source", default="").strip()
        if not source:
            source = _source_from_link(link)
        summary = _clean_html(item.findtext("description", default="").strip())
        out.append(
            {
                "title": item.findtext("title", default="").strip(),
                "link": link,
                "published_at": item.findtext("pubDate", default="").strip(),
                "source": source,
                "summary": summary[: config.ARTICLE_MAX_CHARS],
            }
        )
    return out


def _source_from_link(link: str) -> str:
    try:
        host = urlparse(link).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_news_rss_google(symbol: str) -> list[dict[str, str]]:
    query = f"{symbol} stock"
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(
        rss_url,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    return _parse_rss_items(resp.content)


def _fetch_news_rss_yahoo(symbol: str) -> list[dict[str, str]]:
    rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={quote(symbol)}&region=US&lang=en-US"
    resp = requests.get(
        rss_url,
        timeout=config.REQUEST_TIMEOUT_SEC,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TradingAgent/1.0)"},
    )
    resp.raise_for_status()
    return _parse_rss_items(resp.content)


def _fetch_news_rss(symbol: str) -> tuple[list[dict[str, str]], str, list[str]]:
    errors: list[str] = []
    try:
        rows = _fetch_news_rss_yahoo(symbol)
        if rows:
            return rows, "yahoo_rss", errors
        errors.append("yahoo_rss: empty response")
    except Exception as ex:
        errors.append(f"yahoo_rss: {ex}")

    try:
        rows = _fetch_news_rss_google(symbol)
        if rows:
            return rows, "google_news_rss", errors
        errors.append("google_news_rss: empty response")
    except Exception as ex:
        errors.append(f"google_news_rss: {ex}")

    return [], "none", errors


def _normalize_article_url(url: str) -> str:
    if not url:
        return ""
    p = urlparse(url)
    keep_parts: list[str] = []
    for part in (p.query or "").split("&"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("."):
            continue
        if part.lower().startswith("tsrc="):
            continue
        keep_parts.append(part)
    clean_query = "&".join(keep_parts)
    return urlunparse((p.scheme, p.netloc, p.path, "", clean_query, ""))


def _extract_article_text(url: str) -> tuple[str, str, str]:
    if not url:
        return "", "missing_url", "none"
    target = _normalize_article_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }
    try:
        resp = requests.get(target, timeout=config.REQUEST_TIMEOUT_SEC, headers=headers, allow_redirects=True)
        resp.raise_for_status()
    except Exception as ex:
        return "", f"http_error: {ex}", "http_error"

    soup = BeautifulSoup(resp.text, "html.parser")
    candidates = [
        ("article", soup.find("article")),
        ("itemprop_articleBody", soup.select_one('[itemprop="articleBody"]')),
        ("caas-body", soup.select_one(".caas-body")),
        ("article-body", soup.select_one(".article-body")),
        ("story-body", soup.select_one(".story-body")),
        ("body-copy", soup.select_one(".body-copy")),
    ]
    for method, node in candidates:
        if not node:
            continue
        parts = [p.get_text(" ", strip=True) for p in node.find_all("p")]
        parts = [p for p in parts if len(p) > 20]
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if len(text) >= 120:
            return text[: config.ARTICLE_MAX_CHARS], "", method

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        blobs = payload if isinstance(payload, list) else [payload]
        for blob in blobs:
            if not isinstance(blob, dict):
                continue
            body = str(blob.get("articleBody", "")).strip()
            if len(body) >= 120:
                body = re.sub(r"\s+", " ", body)
                return body[: config.ARTICLE_MAX_CHARS], "", "jsonld_articleBody"

    return "", "no_extractable_content", "none"


def _parse_model_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        raise ValueError("Model returned empty content.")

    # Try direct JSON first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Handle ```json ... ``` wrappers.
    if text.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            text = cleaned

    # Try extracting first JSON object from mixed text.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        return json.loads(candidate)

    preview = text[:220].replace("\n", " ")
    raise ValueError(f"Model did not return parseable JSON. Raw preview: {preview}")


def parse_model_json(content: str) -> dict[str, Any]:
    return _parse_model_json(content)


def _ai_market_view(
    symbol: str,
    history: list[dict[str, Any]],
    news: list[dict[str, Any]],
    holding_shares: float,
    holding_value: float,
) -> dict[str, Any]:
    last_close = history[-1]["close"] if history else 0.0
    prev_close = history[-2]["close"] if len(history) > 1 else last_close
    change_pct = ((last_close - prev_close) / prev_close * 100.0) if prev_close else 0.0

    headlines = "\n".join(f"- {n.get('title', '')}" for n in news)
    snippets = "\n".join(
        f"- {n.get('title', '')}: {n.get('article_text', '')[:500]}"
        for n in news
        if n.get("article_text")
    )
    prompt = (
        "You are a market research agent.\n"
        f"Ticker: {symbol}\n"
        f"Latest close: {last_close:.2f}\n"
        f"1-day change %: {change_pct:.2f}\n\n"
        f"Portfolio context:\n- Shares held: {holding_shares}\n- Position value (USD): {holding_value:.2f}\n\n"
        f"Headlines:\n{headlines}\n\n"
        f"Article snippets:\n{snippets or '- No snippets available'}\n\n"
        "Return strict JSON with keys: summary, sentiment, action_bias, confidence, portfolio_action_plan, portfolio_justification.\n"
        "sentiment must be bullish/neutral/bearish.\n"
        "action_bias must be buy/hold/sell.\n"
        "portfolio_action_plan must be one of: add, hold, reduce, exit.\n"
        "confidence must be integer 0-100."
    )

    content = chat_text("Return valid JSON only.", prompt, temperature=0.1)
    parsed = _parse_model_json(content)
    sentiment = str(parsed.get("sentiment", "neutral")).lower()
    action_bias = str(parsed.get("action_bias", "hold")).lower()
    portfolio_action_plan = str(parsed.get("portfolio_action_plan", "")).lower()
    portfolio_justification = str(parsed.get("portfolio_justification", "")).strip()
    confidence = int(parsed.get("confidence", 50))
    if sentiment not in {"bullish", "neutral", "bearish"}:
        raise ValueError(f"Invalid sentiment from model: {sentiment}")
    if action_bias not in {"buy", "hold", "sell"}:
        raise ValueError(f"Invalid action_bias from model: {action_bias}")
    if portfolio_action_plan not in {"add", "hold", "reduce", "exit"}:
        raise ValueError(f"Invalid portfolio_action_plan from model: {portfolio_action_plan}")
    if not portfolio_justification:
        raise ValueError("Model returned empty portfolio_justification.")
    confidence = max(0, min(confidence, 100))
    return {
        "summary": str(parsed.get("summary", "No summary returned.")),
        "sentiment": sentiment,
        "action_bias": action_bias,
        "portfolio_action_plan": portfolio_action_plan,
        "portfolio_justification": portfolio_justification,
        "confidence": confidence,
        "current_price": round(last_close, 2),
        "price_change_1d_pct": round(change_pct, 2),
        "source": config.AI_PROVIDER,
    }


def run_market_agent(holdings: dict[str, Any]) -> dict[str, Any]:
    tickers = holdings.get("tickers", [])
    holding_shares_map = {k.upper(): float(v) for k, v in holdings.get("shares", {}).items()}
    holding_values_map = {k.upper(): float(v) for k, v in holdings.get("values", {}).items()}
    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers,
        "holdings_source": holdings.get("source", "unknown"),
        "holdings": {},
        "stocks": {},
        "errors": {},
    }

    for symbol in tickers:
        history: list[dict[str, Any]] = []
        news: list[dict[str, Any]] = []
        ticker_errors: list[str] = []
        price_source = "none"
        news_source = "none"

        history, price_source, price_errors = _fetch_price_history(symbol)
        if price_errors:
            ticker_errors.append("price_history: " + " ; ".join(price_errors))

        news, news_source, news_errors = _fetch_news_rss(symbol)
        if news_errors:
            ticker_errors.append("news_rss: " + " ; ".join(news_errors))

        for idx, n in enumerate(news):
            if idx < config.SCRAPE_ARTICLE_COUNT:
                text, err, method = _extract_article_text(n.get("link", ""))
                n["article_text"] = text
                n["article_extract_method"] = method
                if err:
                    n["article_extract_error"] = err
            else:
                n["article_text"] = ""
                n["article_extract_method"] = "skipped"
        extract_errors = [n.get("article_extract_error", "") for n in news if n.get("article_extract_error")]
        if extract_errors:
            ticker_errors.append(
                "article_extract: "
                + "; ".join(extract_errors[:3])
                + (f" (and {len(extract_errors) - 3} more)" if len(extract_errors) > 3 else "")
            )

        ai_view = None
        shares = holding_shares_map.get(symbol.upper(), 0.0)
        position_value = holding_values_map.get(symbol.upper(), 0.0)
        if position_value <= 0 and history and shares > 0:
            position_value = shares * float(history[-1].get("close", 0) or 0)

        if history or news:
            try:
                ai_view = _ai_market_view(symbol, history, news, shares, position_value)
            except Exception as ex:
                ticker_errors.append(f"ai_view: {ex}")

        result["holdings"][symbol] = {
            "shares": round(shares, 6),
            "position_value": round(position_value, 2),
        }
        result["stocks"][symbol] = {
            "history": history,
            "price_source": price_source,
            "current_price": round(float(history[-1]["close"]), 2) if history else None,
            "news": news,
            "news_source": news_source,
            "ai_view": ai_view,
        }

        if ticker_errors:
            result["errors"][symbol] = " | ".join(ticker_errors)

    out_path = config.DATA_DIR / "agent_market_view.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


def get_market_snapshot(symbol: str, article_count: int | None = None) -> dict[str, Any]:
    if article_count is None:
        article_count = config.SCRAPE_ARTICLE_COUNT

    errors: list[str] = []
    history, price_source, price_errors = _fetch_price_history(symbol)
    if price_errors:
        errors.append("price_history: " + " ; ".join(price_errors))

    news, news_source, news_errors = _fetch_news_rss(symbol)
    if news_errors:
        errors.append("news_rss: " + " ; ".join(news_errors))

    for idx, n in enumerate(news):
        if idx < article_count:
            text, err, method = _extract_article_text(n.get("link", ""))
            n["article_text"] = text
            n["article_extract_method"] = method
            if err:
                n["article_extract_error"] = err
        else:
            n["article_text"] = ""
            n["article_extract_method"] = "skipped"

    return {
        "history": history,
        "price_source": price_source,
        "news": news,
        "news_source": news_source,
        "errors": errors,
    }
