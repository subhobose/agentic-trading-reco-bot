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
DAILY_REPORT_FILE = REPORTS_DIR / "daily_report.md"

load_dotenv(dotenv_path=BASE_DIR / ".env")

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "")

USE_ROBINHOOD = os.getenv("USE_ROBINHOOD", "true").lower() == "true"
RH_USERNAME = os.getenv("RH_USERNAME", "")
RH_PASSWORD = os.getenv("RH_PASSWORD", "")
RH_MFA_CODE = os.getenv("RH_MFA_CODE", "")

HISTORY_PERIOD = os.getenv("HISTORY_PERIOD", "6mo")
HISTORY_INTERVAL = os.getenv("HISTORY_INTERVAL", "1d")
NEWS_PER_TICKER = int(os.getenv("NEWS_PER_TICKER", "8"))

SCHEDULE_TIME = os.getenv("SCHEDULE_TIME", "18:00")

