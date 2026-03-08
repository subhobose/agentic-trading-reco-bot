from __future__ import annotations

import argparse
import contextlib
import io
import json
import smtplib
import traceback
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import config
from main import run as run_pipeline


def _append_log(text: str) -> None:
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with config.RUN_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def _log_event(title: str, details: str = "") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"[{now}] {title}"
    if details:
        block += f"\n{details}"
    _append_log(block + "\n" + ("-" * 80))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _build_email_html(success: bool, details: str = "") -> str:
    market = _load_json(config.DATA_DIR / "agent_market_view.json")
    opp = _load_json(config.OPPORTUNITY_FILE)
    generated = market.get("generated_at", datetime.now().isoformat())

    stocks = market.get("stocks", {})
    holdings = market.get("holdings", {})
    buy_ideas = opp.get("buy_ideas", [])
    short_ideas = opp.get("short_ideas", [])

    grouped: dict[str, list[str]] = {"add": [], "hold": [], "reduce": [], "exit": []}
    for symbol, payload in stocks.items():
        ai = payload.get("ai_view", {}) or {}
        plan = str(ai.get("portfolio_action_plan", "hold")).lower()
        if plan in grouped:
            grouped[plan].append(symbol)
        else:
            grouped["hold"].append(symbol)

    def _pill(text: str, bg: str, fg: str = "#08101d") -> str:
        return (
            f"<span style='display:inline-block;margin:4px 6px 0 0;padding:4px 10px;"
            f"border-radius:999px;background:{bg};color:{fg};font-weight:700;font-size:12px'>{text}</span>"
        )

    def _render_group(symbols: list[str], bg: str, empty_label: str = "None") -> str:
        if not symbols:
            return _pill(empty_label, "#2f3f66", "#d5e2ff")
        return "".join(_pill(s, bg) for s in symbols)

    def _idea_list(rows: list[dict[str, Any]], action: str) -> str:
        if not rows:
            return "<li>None</li>"
        parts = []
        for r in rows[:3]:
            parts.append(
                "<li>"
                f"<b>{r.get('symbol', '')}</b> ({action}, {r.get('confidence', 0)}%, ${r.get('current_price', 0)}): "
                f"{r.get('reason', '')}"
                "</li>"
            )
        return "".join(parts)

    status_color = "#2cffb6" if success else "#ff2e63"
    status_label = "SUCCESS" if success else "FAILED"

    return f"""
<html>
  <body style="font-family:Arial,sans-serif;background:#0d1429;color:#e9f1ff;padding:16px;">
    <h2 style="margin:0 0 8px 0;">Daily Trading Agent Run</h2>
    <p style="margin:0 0 12px 0;">Generated: {generated}</p>
    <p style="margin:0 0 12px 0;">
      <b>Status:</b> <span style="padding:3px 8px;border-radius:999px;background:{status_color};color:#08101d;">{status_label}</span>
    </p>
    <p style="margin:0 0 12px 0;">Dashboard URL: <a href="{config.DASHBOARD_URL}">{config.DASHBOARD_URL}</a></p>
    <p style="margin:0 0 16px 0;">{details}</p>

    <h3 style="margin:16px 0 8px 0;">Dashboard Snippet</h3>
    <div style="background:#121c37;border:1px solid #2f3f66;border-radius:10px;padding:12px;">
      <div style="margin-bottom:8px;"><b>ADD:</b> {_render_group(grouped['add'], '#2cffb6')}</div>
      <div style="margin-bottom:8px;"><b>REDUCE:</b> {_render_group(grouped['reduce'], '#ff7b98')}</div>
      <div style="margin-bottom:8px;"><b>EXIT:</b> {_render_group(grouped['exit'], '#ff2e63', 'None')}</div>
      <div><b>HOLD:</b> {_render_group(grouped['hold'], '#ffd166')}</div>
    </div>

    <h3 style="margin:16px 0 8px 0;">Top Buy Ideas</h3>
    <ul style="margin:0 0 10px 18px;">{_idea_list(buy_ideas, "BUY")}</ul>

    <h3 style="margin:12px 0 8px 0;">Top Short Ideas</h3>
    <ul style="margin:0 0 10px 18px;">{_idea_list(short_ideas, "SHORT")}</ul>
  </body>
</html>
""".strip()


def _send_email(subject: str, body_html: str, body_text: str) -> None:
    if not (config.SMTP_HOST and config.SMTP_USERNAME and config.SMTP_PASSWORD and config.EMAIL_TO):
        msg = "[daily_runner] SMTP not configured. Skipping email."
        print(msg)
        _log_event("SMTP skipped", msg)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_FROM or config.SMTP_USERNAME
    msg["To"] = config.EMAIL_TO
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        if config.SMTP_USE_TLS:
            server.starttls()
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.send_message(msg)
    _log_event("Email sent", f"Subject: {subject}\nTo: {config.EMAIL_TO}")


def _send_failure_email_safe(subject: str, html: str, text: str) -> None:
    try:
        _send_email(subject, html, text)
    except Exception as ex:
        msg = f"[daily_runner] Failed to send failure email: {ex}"
        print(msg)
        _log_event("Failure email send error", msg)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trading agent pipeline and/or email summary.")
    parser.add_argument(
        "--email-only",
        action="store_true",
        help="Skip pipeline run and send email from last generated files only.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _log_event("Run started", f"Mode: {'email-only' if args.email_only else 'full'}")
    if args.email_only:
        subject = f"[TEST] Trading Agent Email-Only - {now}"
        html = _build_email_html(True, "Email-only test from last generated files.")
        text = "Email-only test from last generated files."
        _send_email(subject, html, text)
        print("[daily_runner] Email-only test sent.")
        _log_event("Run completed", "Email-only test sent.")
        return

    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            run_pipeline()
        pipeline_output = buf.getvalue().strip()
        if pipeline_output:
            _log_event("Pipeline output", pipeline_output)
        subject = f"[SUCCESS] Trading Agent Daily Run - {now}"
        html = _build_email_html(True, "Pipeline completed and report/dashboard data were generated.")
        text = "Trading Agent completed successfully. See HTML section for dashboard summary."
        _send_email(subject, html, text)
        print("[daily_runner] Completed successfully.")
        _log_event("Run completed", "Status: SUCCESS")
    except Exception:
        err = traceback.format_exc()
        _log_event("Run failed", err)
        subject = f"[FAILED] Trading Agent Daily Run - {now}"
        html = _build_email_html(False, f"<pre>{err}</pre>")
        text = f"Trading Agent failed.\n\n{err}"
        _send_failure_email_safe(subject, html, text)
        print("[daily_runner] Failed.")
        raise


if __name__ == "__main__":
    main()
