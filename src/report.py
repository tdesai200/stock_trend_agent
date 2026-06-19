from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable


def write_daily_report(report_date: date, rows: Iterable[dict], reports_dir: Path) -> Path:
    daily_dir = reports_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    output_path = daily_dir / f"{report_date.isoformat()}.md"

    header = [
        f"# Daily Stock Trend Report - {report_date.isoformat()}",
        "",
        "This output is decision support, not financial advice.",
        "Final conviction is blocked unless technicals are supported by macro news, earnings, fundamentals, and company news inputs.",
        "",
        "| Symbol | Trend | Final Decision | Technical Signal | News Sentiment | Macro Status | Earnings Status | Fundamentals Status | Status | Confidence | RSI(14) | Missing Domains | Reasons | Criteria |",
        "|---|---|---|---|---|---|---|---|---:|---:|---|---|---|",
    ]

    body = []
    for row in rows:
        reasons = ", ".join(row["reasons"])
        missing_domains = ", ".join(row["missing_domains"])
        body.append(
            f"| {row['symbol']} | {row['trend_state']} | {row['suggestion']} | {row['technical_signal']} | {row['news_sentiment']} | {row.get('macro_status', 'unknown')} | {row['earnings_status']} | {row['fundamentals_status']} | {row['decision_status']} | {row['confidence']:.2f} | {row['rsi_14']:.2f} | {missing_domains} | {reasons} | {row['criteria_summary']} |"
        )

        if row["news_headlines"]:
            body.append(f"|  |  |  |  |  |  |  |  |  | Headlines: {'; '.join(row['news_headlines'])} |  |")

        if row["earnings_summary"]:
            body.append(f"|  |  |  |  |  |  |  |  |  |  | Earnings: {row['earnings_summary']} |  |")

        if row["fundamentals_summary"]:
            body.append(
                f"|  |  |  |  |  |  |  |  |  |  | Fundamentals: {row['fundamentals_summary']} |  |"
            )

        if row.get("macro_summary"):
            body.append(f"|  |  |  |  |  |  |  |  |  |  | Macro: {row['macro_summary']} |  |")

    output_path.write_text("\n".join(header + body) + "\n", encoding="utf-8")
    return output_path
