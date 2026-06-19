from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import DEFAULT_CONFIG
from src.data_ingestion import ingest_daily_ohlcv, save_raw_snapshot
from src.earnings_agent import fetch_earnings_signal
from src.features import add_technical_features
from src.fundamentals_agent import fetch_fundamentals_signal
from src.macro_news_agent import fetch_macro_news_signal
from src.news_agent import fetch_company_news
from src.report import write_daily_report
from src.suggestions import make_suggestion
from src.trend import classify_trend


def run_all(as_of_date: date | None = None) -> Path:
    target_date = as_of_date or date.today()
    raw_dir = DEFAULT_CONFIG.data_dir / "raw" / target_date.isoformat()
    processed_dir = DEFAULT_CONFIG.data_dir / "processed" / target_date.isoformat()
    processed_dir.mkdir(parents=True, exist_ok=True)

    report_rows = []

    for symbol in DEFAULT_CONFIG.symbols:
        ohlcv = ingest_daily_ohlcv(
            symbol=symbol,
            as_of_date=target_date,
            source=DEFAULT_CONFIG.market_data_source,
        )
        save_raw_snapshot(df=ohlcv, output_dir=raw_dir, symbol=symbol)

        features = add_technical_features(ohlcv)
        features.to_csv(processed_dir / f"{symbol}.csv", index=False)

        latest = features.dropna().iloc[-1]
        trend_result = classify_trend(latest)
        news_result = fetch_company_news(
            symbol=symbol,
            source=DEFAULT_CONFIG.news_data_source,
            trusted_provider_domains=DEFAULT_CONFIG.trusted_news_provider_domains,
        )
        earnings_result = fetch_earnings_signal(
            symbol=symbol,
            source=DEFAULT_CONFIG.earnings_data_source,
            as_of_date=datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc),
        )
        fundamentals_result = fetch_fundamentals_signal(
            symbol=symbol,
            source=DEFAULT_CONFIG.fundamentals_data_source,
        )
        macro_result = fetch_macro_news_signal(
            source=DEFAULT_CONFIG.macro_news_data_source,
            trusted_provider_domains=DEFAULT_CONFIG.trusted_news_provider_domains,
            feed_urls=DEFAULT_CONFIG.external_news_rss_feeds,
        )

        available_domains = ["technicals"]
        if news_result.status == "trusted_news_available":
            available_domains.append("company_news")
        if earnings_result.status == "earnings_data_available":
            available_domains.append("earnings")
        if fundamentals_result.status == "fundamentals_data_available":
            available_domains.append("fundamentals")
        if macro_result.status == "macro_news_available":
            available_domains.append("macro_news")

        atr_ratio = float(latest["atr_14"] / latest["close"])
        suggestion = make_suggestion(
            trend=trend_result,
            atr_ratio=atr_ratio,
            momentum_5=float(latest["momentum_5"]),
            rsi_14=float(latest["rsi_14"]),
            news_sentiment=news_result.sentiment,
            news_confidence_delta=news_result.confidence_delta,
            news_reasons=news_result.reasons,
            news_status=news_result.status,
            earnings_confidence_delta=earnings_result.confidence_delta,
            earnings_reasons=earnings_result.reasons,
            earnings_status=earnings_result.status,
            earnings_summary=earnings_result.summary,
            fundamentals_confidence_delta=fundamentals_result.confidence_delta,
            fundamentals_reasons=fundamentals_result.reasons,
            fundamentals_status=fundamentals_result.status,
            fundamentals_summary=fundamentals_result.summary,
            macro_confidence_delta=macro_result.confidence_delta,
            macro_reasons=macro_result.reasons,
            macro_status=macro_result.status,
            macro_summary=macro_result.summary,
            available_domains=tuple(available_domains),
            required_domains=DEFAULT_CONFIG.required_decision_domains,
            enforce_full_context=DEFAULT_CONFIG.enforce_full_decision_context,
        )

        report_rows.append(
            {
                "symbol": symbol,
                "trend_state": trend_result.trend_state,
                "suggestion": suggestion.suggestion,
                "technical_signal": suggestion.technical_signal,
                "decision_status": suggestion.decision_status,
                "confidence": suggestion.confidence,
                "rsi_14": suggestion.rsi_14,
                "news_sentiment": suggestion.news_sentiment,
                "news_status": suggestion.news_status,
                "news_headlines": news_result.headlines[:2],
                "earnings_status": suggestion.earnings_status,
                "earnings_summary": suggestion.earnings_summary,
                "latest_surprise_pct": earnings_result.latest_surprise_pct,
                "days_to_next_earnings": earnings_result.days_to_next_earnings,
                "fundamentals_status": suggestion.fundamentals_status,
                "fundamentals_summary": suggestion.fundamentals_summary,
                "macro_status": macro_result.status,
                "macro_summary": macro_result.summary,
                "reasons": suggestion.reasons,
                "criteria_summary": suggestion.criteria_summary,
                "missing_domains": suggestion.missing_domains,
            }
        )

    return write_daily_report(
        report_date=target_date,
        rows=report_rows,
        reports_dir=DEFAULT_CONFIG.reports_dir,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stock trend agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_all_parser = subparsers.add_parser("run-all", help="Run the full daily pipeline")
    run_all_parser.add_argument(
        "--date",
        dest="as_of_date",
        help="Date in YYYY-MM-DD format (default: today)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "run-all":
        selected_date = date.fromisoformat(args.as_of_date) if args.as_of_date else None
        report_path = run_all(as_of_date=selected_date)
        print(f"Daily report generated: {report_path}")


if __name__ == "__main__":
    main()
