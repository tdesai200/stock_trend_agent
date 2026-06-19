from __future__ import annotations

import contextlib
from datetime import date
import io
from pathlib import Path
import os

import pandas as pd
import requests
import yfinance as yf

from src.config import DEFAULT_CONFIG


def _tag_market_data(df: pd.DataFrame, status: str, detail: str) -> pd.DataFrame:
    df.attrs["market_data_status"] = status
    df.attrs["market_data_detail"] = detail
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        # Keep price field names and drop ticker-level suffix for single-symbol fetches.
        df.columns = [str(col[0]).lower() for col in df.columns]
    else:
        df.columns = [str(col).lower() for col in df.columns]
    return df


def _validate_source(source: str) -> None:
    if source not in DEFAULT_CONFIG.trusted_data_sources:
        allowed = ", ".join(DEFAULT_CONFIG.trusted_data_sources)
        raise ValueError(f"Untrusted source={source}. Allowed sources: {allowed}")

    if source != "yfinance":
        raise ValueError(f"Source={source} is allowed but not yet implemented")


def _load_cached_raw_snapshot(symbol: str, as_of_date: date) -> pd.DataFrame:
    raw_root = DEFAULT_CONFIG.data_dir / "raw"
    if not raw_root.exists():
        raise ValueError(f"No cached raw data is available for symbol={symbol}")

    candidate_files = sorted(raw_root.glob(f"*/{symbol}.csv"), reverse=True)
    for candidate in candidate_files:
        try:
            cached = pd.read_csv(candidate)
        except Exception:
            continue

        cached = _normalize_columns(cached)
        if "date" not in cached.columns:
            continue

        cached["date"] = pd.to_datetime(cached["date"], errors="coerce")
        cached = cached.dropna(subset=["date"]).sort_values("date")
        cached = cached[cached["date"].dt.date <= as_of_date]
        if cached.empty:
            continue

        cached["date"] = cached["date"].dt.date
        cached["symbol"] = symbol
        print(
            f"[WARNING] Live market data unavailable for {symbol}. "
            f"Using cached snapshot from {candidate.parent.name}."
        )
        return _tag_market_data(
            cached.reset_index(drop=True),
            status="cached_snapshot",
            detail=f"Using cached snapshot from {candidate.parent.name}.",
        )

    raise ValueError(
        f"No live data returned for symbol={symbol} and no cached raw snapshot was available on or before {as_of_date.isoformat()}"
    )


def _allow_insecure_price_ssl() -> bool:
    return os.getenv("PRICE_ALLOW_INSECURE_SSL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _persist_raw_cache_snapshot(df: pd.DataFrame, symbol: str, as_of_date: date) -> None:
    try:
        raw_dir = DEFAULT_CONFIG.data_dir / "raw" / as_of_date.isoformat()
        raw_dir.mkdir(parents=True, exist_ok=True)
        output_path = raw_dir / f"{symbol}.csv"
        df.to_csv(output_path, index=False)
    except Exception as exc:
        print(f"[WARNING] Could not save raw cache snapshot for {symbol}: {exc}")


def _load_yahoo_chart_fallback(symbol: str, as_of_date: date) -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
    }

    request_kwargs = {"timeout": 20, "headers": headers}
    if _allow_insecure_price_ssl():
        request_kwargs["verify"] = False

    response = requests.get(url, **request_kwargs)
    response.raise_for_status()
    payload = response.json()

    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError(f"Yahoo chart fallback returned no result for symbol={symbol}")

    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [None])[0]
    if not timestamps or not quote:
        raise ValueError(f"Yahoo chart fallback returned incomplete data for symbol={symbol}")

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None),
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "volume": quote.get("volume"),
        }
    )

    adjclose = ((result.get("indicators") or {}).get("adjclose") or [None])[0]
    if adjclose and adjclose.get("adjclose"):
        frame["adj close"] = adjclose.get("adjclose")
    else:
        frame["adj close"] = frame["close"]

    frame = frame.dropna(subset=["date", "close"]).sort_values("date")
    frame = frame[frame["date"].dt.date <= as_of_date]
    if frame.empty:
        raise ValueError(f"Yahoo chart fallback returned no rows on or before {as_of_date.isoformat()} for symbol={symbol}")

    frame["date"] = frame["date"].dt.date
    frame["symbol"] = symbol
    persisted_frame = frame.reset_index(drop=True)
    _persist_raw_cache_snapshot(persisted_frame, symbol=symbol, as_of_date=as_of_date)
    print(f"[WARNING] Live yfinance data unavailable for {symbol}. Using Yahoo chart endpoint fallback.")
    return _tag_market_data(
        persisted_frame,
        status="yahoo_chart_fallback",
        detail=f"Using Yahoo chart endpoint fallback for the latest available online data and saved snapshot to data/raw/{as_of_date.isoformat()}/{symbol}.csv.",
    )


def ingest_daily_ohlcv(symbol: str, as_of_date: date, source: str) -> pd.DataFrame:
    """Fetches 6 months of daily OHLCV data for one symbol."""
    _validate_source(source)

    end_date = as_of_date.isoformat()
    start = pd.Timestamp(as_of_date) - pd.Timedelta(days=190)

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            data = yf.download(
                tickers=symbol,
                start=start.date().isoformat(),
                end=end_date,
                interval="1d",
                auto_adjust=False,
                progress=False,
            )
    except Exception:
        data = pd.DataFrame()

    if data.empty:
        try:
            return _load_cached_raw_snapshot(symbol=symbol, as_of_date=as_of_date)
        except ValueError as cached_exc:
            try:
                return _load_yahoo_chart_fallback(symbol=symbol, as_of_date=as_of_date)
            except Exception as chart_exc:
                raise ValueError(
                    f"No live data returned for symbol={symbol}; cached snapshot unavailable; "
                    f"Yahoo chart fallback failed: {chart_exc}"
                ) from cached_exc

    data = data.reset_index()
    data = _normalize_columns(data)

    # yfinance may return "datetime" or "date" depending on source shape.
    if "datetime" in data.columns and "date" not in data.columns:
        data = data.rename(columns={"datetime": "date"})

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date")
    data = data[data["date"].dt.date <= as_of_date]

    if data.empty:
        try:
            return _load_cached_raw_snapshot(symbol=symbol, as_of_date=as_of_date)
        except ValueError as cached_exc:
            try:
                return _load_yahoo_chart_fallback(symbol=symbol, as_of_date=as_of_date)
            except Exception as chart_exc:
                raise ValueError(
                    f"No live data returned for symbol={symbol}; cached snapshot unavailable; "
                    f"Yahoo chart fallback failed: {chart_exc}"
                ) from cached_exc

    data["date"] = data["date"].dt.date
    data["symbol"] = symbol
    return _tag_market_data(
        data.reset_index(drop=True),
        status="live_yfinance",
        detail="Using live market data from yfinance.",
    )


def save_raw_snapshot(df: pd.DataFrame, output_dir: Path, symbol: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{symbol}.csv"
    df.to_csv(output_path, index=False)
    return output_path
