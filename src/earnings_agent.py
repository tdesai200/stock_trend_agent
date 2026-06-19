from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class EarningsAgentResult:
    status: str
    confidence_delta: float
    reasons: list[str]
    summary: str
    latest_surprise_pct: float | None
    days_to_next_earnings: int | None


def _safe_timestamp(value: object) -> pd.Timestamp | None:
    if value is None:
        return None

    try:
        ts = pd.to_datetime(value, utc=True)
    except (TypeError, ValueError):
        return None

    if isinstance(ts, pd.Series):
        if ts.empty:
            return None
        ts = ts.iloc[0]

    if pd.isna(ts):
        return None

    if isinstance(ts, pd.Timestamp):
        return ts

    return None


def _extract_next_earnings_days(ticker: yf.Ticker, as_of_date: datetime) -> int | None:
    try:
        calendar = ticker.calendar
    except Exception:
        return None
    next_ts = None

    if isinstance(calendar, pd.DataFrame) and not calendar.empty:
        if "Earnings Date" in calendar.index:
            row = calendar.loc["Earnings Date"]
            if isinstance(row, pd.Series):
                next_ts = _safe_timestamp(row.iloc[0])
            else:
                next_ts = _safe_timestamp(row)
        elif "Earnings Date" in calendar.columns:
            next_ts = _safe_timestamp(calendar["Earnings Date"].iloc[0])

    if next_ts is None and isinstance(calendar, dict):
        next_ts = _safe_timestamp(calendar.get("Earnings Date"))

    if next_ts is None:
        return None

    current_date = pd.Timestamp(as_of_date.date(), tz="UTC")
    days = int((next_ts.normalize() - current_date.normalize()).days)
    return days


def _extract_latest_surprise_pct(ticker: yf.Ticker) -> float | None:
    try:
        earnings_dates = ticker.earnings_dates
    except Exception:
        return None

    if not isinstance(earnings_dates, pd.DataFrame) or earnings_dates.empty:
        return None

    surprise_col = None
    for candidate in ("Surprise(%)", "surprise(%)", "Surprise %"):
        if candidate in earnings_dates.columns:
            surprise_col = candidate
            break

    if surprise_col is None:
        return None

    surprise_series = pd.to_numeric(earnings_dates[surprise_col], errors="coerce").dropna()
    if surprise_series.empty:
        return None

    return float(surprise_series.iloc[0])


def fetch_earnings_signal(symbol: str, source: str, as_of_date: datetime) -> EarningsAgentResult:
    if source != "yfinance":
        raise ValueError(f"Untrusted or unsupported earnings source={source}")

    ticker = yf.Ticker(symbol)
    days_to_next_earnings = _extract_next_earnings_days(ticker=ticker, as_of_date=as_of_date)
    latest_surprise_pct = _extract_latest_surprise_pct(ticker=ticker)

    reasons: list[str] = []
    confidence_delta = 0.0

    if latest_surprise_pct is not None:
        if latest_surprise_pct >= 5:
            confidence_delta += 0.06
            reasons.append("earnings_surprise_positive")
        elif latest_surprise_pct <= -5:
            confidence_delta -= 0.12
            reasons.append("earnings_surprise_negative")
        else:
            reasons.append("earnings_surprise_moderate")

    if days_to_next_earnings is not None:
        if days_to_next_earnings <= 3:
            confidence_delta -= 0.08
            reasons.append("earnings_event_risk_imminent")
        elif days_to_next_earnings <= 7:
            confidence_delta -= 0.04
            reasons.append("earnings_event_risk_near_term")

    if latest_surprise_pct is None and days_to_next_earnings is None:
        return EarningsAgentResult(
            status="no_earnings_data",
            confidence_delta=0.0,
            reasons=["no_earnings_context"],
            summary="No trusted earnings context available",
            latest_surprise_pct=None,
            days_to_next_earnings=None,
        )

    surprise_text = (
        f"latest surprise={latest_surprise_pct:.2f}%" if latest_surprise_pct is not None else "latest surprise=unknown"
    )
    next_text = (
        f"days_to_next_earnings={days_to_next_earnings}" if days_to_next_earnings is not None else "days_to_next_earnings=unknown"
    )

    return EarningsAgentResult(
        status="earnings_data_available",
        confidence_delta=round(confidence_delta, 3),
        reasons=reasons or ["earnings_context_available"],
        summary=f"{surprise_text}; {next_text}",
        latest_surprise_pct=latest_surprise_pct,
        days_to_next_earnings=days_to_next_earnings,
    )