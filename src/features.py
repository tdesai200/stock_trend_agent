from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange


MIN_ROWS_RSI_ATR = 14


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < MIN_ROWS_RSI_ATR:
        raise ValueError(
            f"INSUFFICIENT_HISTORY_14: need at least {MIN_ROWS_RSI_ATR} rows, got {len(df)}"
        )

    features = df.copy()
    close = features["close"]

    features["sma_20"] = SMAIndicator(close=close, window=20).sma_indicator()
    features["sma_50"] = SMAIndicator(close=close, window=50).sma_indicator()
    features["ema_12"] = EMAIndicator(close=close, window=12).ema_indicator()
    features["ema_26"] = EMAIndicator(close=close, window=26).ema_indicator()
    features["rsi_14"] = RSIIndicator(close=close, window=14).rsi()
    features["atr_14"] = AverageTrueRange(
        high=features["high"],
        low=features["low"],
        close=close,
        window=14,
    ).average_true_range()
    features["momentum_5"] = close.pct_change(periods=5)

    return features
