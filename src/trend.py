from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TrendResult:
    trend_state: str
    evidence: list[str]


def classify_trend(latest_row: pd.Series) -> TrendResult:
    close = float(latest_row["close"])
    sma_20 = float(latest_row["sma_20"])
    sma_50 = float(latest_row["sma_50"])
    rsi_14 = float(latest_row["rsi_14"])

    uptrend = close > sma_20 > sma_50 and rsi_14 > 50
    downtrend = close < sma_20 < sma_50 and rsi_14 < 50

    if uptrend:
        return TrendResult(
            trend_state="Uptrend",
            evidence=["price_above_sma20_sma50", "rsi_above_50"],
        )

    if downtrend:
        return TrendResult(
            trend_state="Downtrend",
            evidence=["price_below_sma20_sma50", "rsi_below_50"],
        )

    return TrendResult(
        trend_state="Neutral",
        evidence=["mixed_signal_structure"],
    )
