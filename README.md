# Agentic Trading Reco Bot (Reset - Simple Flow)

This version uses a simple two-agent pipeline:

1. `holdings_agent`:
- Pulls holdings from Robinhood (fallback to `data/portfolio.json`)

2. `market_agent`:
- Scrapes market price history (Yahoo Chart API with Stooq fallback)
- Scrapes news feed (Yahoo RSS with Google News fallback)
- Scrapes article pages from URLs
- Sends scraped context + holdings context to Ollama for `buy/hold/sell` and a holdings-aware portfolio action plan

3. `opportunity_agent`:
- Builds a dynamic ticker universe from live Yahoo screeners (gainers/losers/most active/trending)
- Produces exactly 3 BUY ideas and 3 SHORT ideas with AI-generated catalyst justification
- Uses holdings context (shares and position values) so recommendations consider portfolio spread/concentration

No `yfinance` is used in the active flow.

## Run

```powershell
python main.py
```

Outputs:
- `data/agent_market_view.json`
- `data/opportunity_recommendations.json`
- `reports/daily_report.md`

## Dashboard

Run:

```powershell
python dashboard_server.py
```

Open:

- `http://127.0.0.1:8765/dashboard/`

## Daily Automation (Run + Email)

Use:

```powershell
python daily_runner.py
```

This will:
- run the full pipeline
- write normal output files
- send a success/failure email with a dashboard-style summary

## Required `.env`

```env
USE_ROBINHOOD=true
RH_USERNAME=you@example.com
RH_PASSWORD=your_password
RH_MFA_CODE=

OLLAMA_MODEL=llama3
OLLAMA_HOST=
AI_PROVIDER=ollama
AI_MODEL=llama3

# OpenAI mode (use these when AI_PROVIDER=openai)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1

REQUEST_TIMEOUT_SEC=12
SCRAPE_NEWS_COUNT=8
SCRAPE_ARTICLE_COUNT=3
ARTICLE_MAX_CHARS=3500
DEFAULT_MARKET_SUFFIX=.US
SCAN_UNIVERSE=AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,AVGO,PLTR
SCAN_BUY_COUNT=3
SCAN_SHORT_COUNT=3
SCAN_ARTICLE_COUNT=2
SCAN_TARGET_UNIVERSE_SIZE=40

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_USE_TLS=true
EMAIL_FROM=you@gmail.com
EMAIL_TO=you@gmail.com
DASHBOARD_URL=http://127.0.0.1:8765/dashboard/
```

`SCAN_UNIVERSE` is now a seed/fallback list, not the only list scanned.

For Gmail, use an App Password (not your normal account password).

## AI Provider Switch

- Local Ollama:
  - `AI_PROVIDER=ollama`
  - `AI_MODEL=llama3`
  - `OLLAMA_HOST=http://127.0.0.1:11434` (or blank for default local)

- OpenAI API:
  - `AI_PROVIDER=openai`
  - `OPENAI_API_KEY=...`
  - `OPENAI_MODEL=gpt-4o-mini` (or your preferred model)
  - optional `OPENAI_BASE_URL` if using a compatible endpoint

### Windows Task Scheduler (every morning at 8:00 AM)

```powershell
schtasks /Create /TN "TradingAgentDaily" /SC DAILY /ST 08:00 /TR "\"D:\CodingProjects\TradingAgent\.venv\Scripts\python.exe\" \"D:\CodingProjects\TradingAgent\daily_runner.py\"" /F
```

Run once immediately to test:

```powershell
schtasks /Run /TN "TradingAgentDaily"
```
