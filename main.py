from __future__ import annotations

import argparse
import time

import schedule

import config
from agents.data_collector import collect_market_data
from agents.portfolio_manager import run_portfolio_manager
from agents.risk_agent import run_risk_analysis
from agents.sentiment_agent import run_sentiment_analysis
from agents.technical_agent import run_technical_analysis


def run_pipeline() -> None:
    print("[pipeline] 1/5 Collecting market + portfolio data")
    collect_market_data()
    print("[pipeline] 2/5 Running technical analysis")
    run_technical_analysis()
    print("[pipeline] 3/5 Running sentiment analysis")
    run_sentiment_analysis()
    print("[pipeline] 4/5 Running risk analysis")
    run_risk_analysis()
    print("[pipeline] 5/5 Generating recommendations + report")
    result = run_portfolio_manager()
    print(
        "[pipeline] Completed. Report:",
        config.DAILY_REPORT_FILE,
        "| risk:",
        result.get("overall_risk_level"),
    )


def run_daily_scheduler(schedule_time: str) -> None:
    print(f"[scheduler] Daily run scheduled at {schedule_time}")
    schedule.every().day.at(schedule_time).do(run_pipeline)
    while True:
        schedule.run_pending()
        time.sleep(10)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Free local multi-agent stock analysis system")
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Run as a daily scheduler instead of one immediate run.",
    )
    parser.add_argument(
        "--time",
        default=config.SCHEDULE_TIME,
        help="Daily schedule time in HH:MM (24h). Default from config/env.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.daily:
        run_daily_scheduler(args.time)
    else:
        run_pipeline()

