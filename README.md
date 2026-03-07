<<<<<<< HEAD
# agentic-trading-reco-bot
=======
# Free Local AI Stock Analysis System

Multi-agent Python pipeline that:
- pulls market + portfolio data
- calculates technical indicators
- summarizes news sentiment with Ollama
- evaluates portfolio risk
- generates BUY/HOLD/SELL recommendations
- writes a daily markdown report

## Project Layout

```text
agents/
  data_collector.py
  technical_agent.py
  sentiment_agent.py
  risk_agent.py
  portfolio_manager.py
data/
  portfolio.json
reports/
main.py
config.py
requirements.txt
```

## Setup

1. Activate virtual env (PowerShell):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:
```powershell
pip install -r requirements.txt
```

3. Configure `.env`:
```env
USE_ROBINHOOD=true
RH_USERNAME=you@example.com
RH_PASSWORD=your_password
RH_MFA_CODE=

OLLAMA_MODEL=llama3
OLLAMA_HOST=
SCHEDULE_TIME=18:00
```

Notes:
- If Robinhood login fails or creds are missing, the system automatically falls back to `data/portfolio.json`.
- Keep Ollama running locally before sentiment analysis.

## Run Once

```powershell
python main.py
```

## Run Daily Scheduler

```powershell
python main.py --daily --time 18:00
```

## Output Files

- Market data: `data/stock_data.json`
- Technicals: `data/technical_analysis.json`
- Sentiment: `data/sentiment_analysis.json`
- Risk: `data/risk_report.json`
- Recommendations: `data/recommendations.json`
- Report: `reports/daily_report.md`

## Dashboard

Run:

```powershell
python dashboard_server.py
```

Then open:

- `http://127.0.0.1:8765/dashboard/`

The dashboard reads the latest JSON outputs and renders:
- allocation by position value
- recommendation table
- RSI snapshot
- sentiment confidence