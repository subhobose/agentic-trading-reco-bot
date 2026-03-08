from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
AGENTS_DIR = BASE_DIR / "agents"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
STOCK_DATA_FILE = DATA_DIR / "stock_data.json"
TECHNICAL_FILE = DATA_DIR / "technical_analysis.json"
SENTIMENT_FILE = DATA_DIR / "sentiment_analysis.json"
RISK_FILE = DATA_DIR / "risk_report.json"
RECOMMENDATION_FILE = DATA_DIR / "recommendations.json"
OPPORTUNITY_FILE = DATA_DIR / "opportunity_recommendations.json"
DAILY_REPORT_FILE = REPORTS_DIR / "daily_report.md"
RUN_LOG_FILE = REPORTS_DIR / "run_log.txt"

load_dotenv(dotenv_path=BASE_DIR / ".env")

AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip().lower()
DEFAULT_MODEL = os.getenv(
    "AI_MODEL",
    os.getenv("OLLAMA_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "6"))
OPENAI_RETRY_BASE_SEC = float(os.getenv("OPENAI_RETRY_BASE_SEC", "2"))

USE_ROBINHOOD = os.getenv("USE_ROBINHOOD", "true").lower() == "true"
RH_USERNAME = os.getenv("RH_USERNAME", "")
RH_PASSWORD = os.getenv("RH_PASSWORD", "")
RH_MFA_CODE = os.getenv("RH_MFA_CODE", "")

ARTICLE_TIMEOUT_SEC = int(os.getenv("ARTICLE_TIMEOUT_SEC", "8"))
ARTICLE_MAX_CHARS = int(os.getenv("ARTICLE_MAX_CHARS", "3500"))

# Simple scraping-agent settings (new active flow)
REQUEST_TIMEOUT_SEC = int(os.getenv("REQUEST_TIMEOUT_SEC", "12"))
SCRAPE_ARTICLE_COUNT = int(os.getenv("SCRAPE_ARTICLE_COUNT", "5"))
SCRAPE_NEWS_COUNT = int(os.getenv("SCRAPE_NEWS_COUNT", "5"))
DEFAULT_MARKET_SUFFIX = os.getenv("DEFAULT_MARKET_SUFFIX", ".US")
SCAN_UNIVERSE = [
    s.strip().upper()
    for s in os.getenv(
        "SCAN_UNIVERSE",
        "AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,AVGO,PLTR,CRM,NFLX,JPM,V,MA,UNH,XOM,COST,WMT,UBER",
    ).split(",")
    if s.strip()
]
SCAN_BUY_COUNT = int(os.getenv("SCAN_BUY_COUNT", "3"))
SCAN_SHORT_COUNT = int(os.getenv("SCAN_SHORT_COUNT", "3"))
SCAN_ARTICLE_COUNT = int(os.getenv("SCAN_ARTICLE_COUNT", "2"))
SCAN_TARGET_UNIVERSE_SIZE = int(os.getenv("SCAN_TARGET_UNIVERSE_SIZE", "40"))

# Daily automation + email settings
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USERNAME)
EMAIL_TO = os.getenv("EMAIL_TO", "")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:8765/dashboard/")
