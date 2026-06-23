from __future__ import annotations

import atexit
from datetime import date, datetime, timezone
import json
import os
import re
import signal
import socket
import subprocess
import threading
import time
import uuid
import webbrowser
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
from dash import Dash, Input, Output, State, dash_table, dcc, html
from dash.dependencies import ALL

from src.chat_agent import answer_question, ChatResponse, EXAMPLE_QUESTIONS
from src.config import DEFAULT_CONFIG
from src.data_ingestion import ingest_daily_ohlcv
from src.earnings_agent import fetch_earnings_signal
from src.features import add_technical_features
from src.fundamentals_agent import fetch_fundamentals_signal
from src.macro_news_agent import fetch_macro_news_signal
from src.news_agent import fetch_company_news
from src.news_filter import get_claude_status
from src.suggestions import make_suggestion
from src.trend import classify_trend

# Load environment variables from .env when python-dotenv is available.
if load_dotenv is not None:
    load_dotenv(override=True)
    #load_dotenv()


MIN_ROWS_RSI_ATR = 14
MIN_ROWS_TREND_MODEL = 50
MAX_TICKERS_PER_REQUEST = 20
MAX_WATCHLIST_SIZE = 20
WATCHLIST_FILE = Path("data") / "watchlist.json"
DAILY_SIGNALS_FILE = Path("data") / "watchlist_daily_signals.json"


def _read_json_file(path: Path, default):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_watchlist() -> list[str]:
    payload = _read_json_file(WATCHLIST_FILE, default={})
    symbols = payload.get("symbols", []) if isinstance(payload, dict) else []
    if not isinstance(symbols, list):
        return []

    cleaned: list[str] = []
    for symbol in symbols:
        token = str(symbol).strip().upper()
        if token and token not in cleaned:
            cleaned.append(token)
    return cleaned


def _save_watchlist(symbols: list[str]) -> None:
    _write_json_file(
        WATCHLIST_FILE,
        {
            "symbols": symbols,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _load_daily_signal_runs() -> list[dict]:
    payload = _read_json_file(DAILY_SIGNALS_FILE, default={})
    runs = payload.get("runs", []) if isinstance(payload, dict) else []
    return runs if isinstance(runs, list) else []


def _save_daily_signal_runs(runs: list[dict]) -> None:
    _write_json_file(
        DAILY_SIGNALS_FILE,
        {
            "runs": runs,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _upsert_daily_signal_run(as_of_date: date, analyzed_rows: list[dict]) -> None:
    run_entry = {
        "date": as_of_date.isoformat(),
        "symbols": [
            {
                "symbol": row["symbol"],
                "trend": row["trend"],
                "final_decision": row["final_decision"],
                "confidence": float(row["confidence"]),
            }
            for row in analyzed_rows
        ],
    }

    runs = _load_daily_signal_runs()
    replaced = False
    for index, existing in enumerate(runs):
        if isinstance(existing, dict) and existing.get("date") == run_entry["date"]:
            runs[index] = run_entry
            replaced = True
            break

    if not replaced:
        runs.append(run_entry)

    runs = sorted(
        [run for run in runs if isinstance(run, dict) and run.get("date")],
        key=lambda run: run["date"],
    )[-30:]
    _save_daily_signal_runs(runs)


def _get_previous_trends(as_of_date: date) -> dict[str, str]:
    runs = _load_daily_signal_runs()
    prior_runs = [run for run in runs if isinstance(run, dict) and str(run.get("date", "")) < as_of_date.isoformat()]
    if not prior_runs:
        return {}

    latest_prior = sorted(prior_runs, key=lambda run: str(run.get("date", "")))[-1]
    trend_map: dict[str, str] = {}
    for row in latest_prior.get("symbols", []):
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        trend = str(row.get("trend", "")).strip().lower()
        if symbol and trend:
            trend_map[symbol] = trend
    return trend_map


def _build_watchlist_chips(symbols: list[str]):
    if not symbols:
        return html.Span("No watchlist symbols saved yet.", className="watchlist-empty")
    return html.Div([html.Span(symbol, className="watchlist-chip") for symbol in symbols], className="watchlist-chip-row")


def _extract_ticker_from_question(question: str) -> str | None:
    text = (question or "").upper()
    matches = re.findall(r"\b[A-Z0-9\.\-\^]{1,10}\b", text)
    if not matches:
        return None

    ignored = {
        "A", "I", "AN", "AND", "ARE", "AS", "AT", "BE", "BUY", "CAN", "DID", "DO",
        "FOR", "FROM", "HAS", "HAVE", "HOW", "IF", "IN", "IS", "IT", "MY", "OF",
        "ON", "OR", "OUT", "SHOW", "THE", "THIS", "TO", "UP", "WHY", "WHAT", "WHEN",
        "WHERE", "WHO", "WITH", "YOUR", "TEND", "TREND", "DOWN", "UPTREND", "DOWNTREND",
    }

    for token in matches:
        if token in ignored:
            continue
        if len(token) <= 1:
            continue
        return token

    return None


def _build_question_context_from_ticker(question: str, as_of_date: date, use_claude_filter: bool) -> dict:
    ticker = _extract_ticker_from_question(question)
    if not ticker:
        return {}

    try:
        result = analyze_symbol(symbol=ticker, as_of_date=as_of_date, use_claude_filter=use_claude_filter)
    except Exception:
        return {}

    macro_label, _, _ = _macro_meter_payload(result.get("macro_status", ""), result.get("macro_summary", ""))
    return {
        "symbol": result["symbol"],
        "final_decision": result["final_decision"],
        "confidence": result["confidence"],
        "trend": result["trend"],
        "rsi_14": result["rsi_14"],
        "technical_signal": result["technical_signal"],
        "criteria": result["criteria"],
        "macro_tone": macro_label,
        "macro_summary": result["macro_summary"],
        "news_sentiment": result["news_sentiment"],
        "earnings_summary": result["earnings_summary"],
        "fundamentals_summary": result["fundamentals_summary"],
    }


def _format_trend_badge(trend: str) -> str:
    normalized = (trend or "").strip().lower()
    if normalized == "uptrend":
        return "UP  Uptrend"
    if normalized == "downtrend":
        return "DOWN  Downtrend"
    return "NEUTRAL  Neutral"


def _format_market_data_badge(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized == "live_yfinance":
        return "LIVE  Yahoo"
    if normalized == "cached_snapshot":
        return "CACHED  Snapshot"
    if normalized == "yahoo_chart_fallback":
        return "FALLBACK  Yahoo Direct"
    return "UNKNOWN  Source"


def _parse_criteria_sections(criteria: str) -> dict[str, str]:
    text = (criteria or "").strip()
    sections = {
        "technical": "",
        "risk": "",
        "news": "",
        "earnings": "",
        "fundamentals": "",
        "gating": "",
        "other": [],
    }

    if not text:
        return sections

    for raw_piece in [piece.strip() for piece in text.split(";") if piece.strip()]:
        lowered = raw_piece.lower()
        if "atr/close" in lowered or "penalty" in lowered or "volatility" in lowered:
            sections["risk"] = raw_piece
        elif "final conviction disabled" in lowered or "context is available" in lowered:
            sections["gating"] = raw_piece
        elif lowered.startswith("earnings context:"):
            sections["earnings"] = raw_piece.replace("earnings context:", "", 1).strip()
        elif lowered.startswith("fundamentals context:"):
            sections["fundamentals"] = raw_piece.replace("fundamentals context:", "", 1).strip()
        elif "news" in lowered:
            sections["news"] = raw_piece
        elif any(token in lowered for token in ("uptrend", "downtrend", "rsi", "momentum", "technical")):
            sections["technical"] = raw_piece
        else:
            sections["other"].append(raw_piece)

    return sections


def _extract_macro_score(macro_summary: str) -> float | None:
    text = (macro_summary or "").strip()
    if not text:
        return None

    marker = "avg_macro_score="
    if marker not in text:
        return None

    try:
        raw = text.split(marker, 1)[1].split(";", 1)[0].strip()
        return float(raw)
    except (ValueError, IndexError):
        return None


def _macro_meter_payload(macro_status: str, macro_summary: str) -> tuple[str, str, int]:
    score = _extract_macro_score(macro_summary)

    if macro_status != "macro_news_available" or score is None:
        return ("Unavailable", "No trusted macro-news context found", 50)

    if score >= 0.6:
        label = "Supportive"
    elif score <= -0.6:
        label = "Risk-Off"
    else:
        label = "Neutral"

    # Map score range [-2, 2] to [0, 100] for meter width.
    normalized = max(0, min(100, int(((score + 2.0) / 4.0) * 100)))
    details = f"{macro_summary}"
    return (label, details, normalized)


class GuardrailError(Exception):
    def __init__(self, guardrail_id: str, message: str) -> None:
        self.guardrail_id = guardrail_id
        self.message = message
        super().__init__(f"GUARDRAIL[{guardrail_id}] {message}")


def _validate_ticker_symbol(symbol: str) -> None:
    if not re.fullmatch(r"[A-Z0-9\.\-\^]{1,10}", symbol):
        raise GuardrailError(
            "INVALID_TICKER_FORMAT",
            "Ticker format is invalid. Use letters/numbers and optional ., -, ^ characters.",
        )


def _parse_tickers(raw_tickers: str) -> list[str]:
    parts = [part.strip().upper() for part in raw_tickers.split(",")]
    return [part for part in parts if part]


def _validate_request(tickers: list[str], as_of_date: date) -> None:
    if not tickers:
        raise GuardrailError("EMPTY_TICKER_LIST", "Please provide at least one ticker.")

    if len(tickers) > MAX_TICKERS_PER_REQUEST:
        raise GuardrailError(
            "TOO_MANY_TICKERS",
            f"Too many tickers in one request. Limit is {MAX_TICKERS_PER_REQUEST}.",
        )

    if as_of_date > date.today():
        raise GuardrailError("FUTURE_DATE", "As of date cannot be in the future.")


def analyze_symbol(symbol: str, as_of_date: date, use_claude_filter: bool = True) -> dict:
    _validate_ticker_symbol(symbol)

    ohlcv = ingest_daily_ohlcv(
        symbol=symbol,
        as_of_date=as_of_date,
        source=DEFAULT_CONFIG.market_data_source,
    )

    required_columns = {"date", "open", "high", "low", "close", "volume", "symbol"}
    missing_columns = sorted(required_columns - set(ohlcv.columns))
    if missing_columns:
        raise GuardrailError(
            "MISSING_PRICE_COLUMNS",
            f"Market data is missing required columns: {', '.join(missing_columns)}.",
        )

    if len(ohlcv) < MIN_ROWS_RSI_ATR:
        raise GuardrailError(
            "INSUFFICIENT_HISTORY_14",
            "The ticker you asked for does not have enough history (minimum 14 trading days).",
        )

    if len(ohlcv) < MIN_ROWS_TREND_MODEL:
        raise GuardrailError(
            "INSUFFICIENT_HISTORY_50",
            "The ticker you asked for does not have enough history for 50-day trend features.",
        )

    if (ohlcv["close"] <= 0).any():
        raise GuardrailError(
            "INVALID_CLOSE_PRICE",
            "Ticker data has non-positive close prices and cannot be analyzed safely.",
        )

    market_data_status = ohlcv.attrs.get("market_data_status", "unknown")
    market_data_detail = ohlcv.attrs.get("market_data_detail", "Market data source detail unavailable.")

    try:
        features = add_technical_features(ohlcv)
    except Exception as exc:
        raise GuardrailError(
            "FEATURE_ENGINEERING_FAILED",
            f"Could not build technical features for this ticker: {exc}",
        ) from exc

    cleaned_features = features.dropna()
    if cleaned_features.empty:
        raise GuardrailError(
            "NO_VALID_FEATURE_ROWS",
            "No valid feature rows remain after indicator windows; ticker history is insufficient for this model.",
        )

    latest = cleaned_features.iloc[-1]

    trend_result = classify_trend(latest)
    news_result = fetch_company_news(
        symbol=symbol,
        source=DEFAULT_CONFIG.news_data_source,
        trusted_provider_domains=DEFAULT_CONFIG.trusted_news_provider_domains,
        use_claude_filter=use_claude_filter,
    )
    earnings_result = fetch_earnings_signal(
        symbol=symbol,
        source=DEFAULT_CONFIG.earnings_data_source,
        as_of_date=datetime.combine(as_of_date, datetime.min.time(), tzinfo=timezone.utc),
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

    return {
        "symbol": symbol,
        "trend": trend_result.trend_state,
        "final_decision": suggestion.suggestion,
        "technical_signal": suggestion.technical_signal,
        "confidence": suggestion.confidence,
        "rsi_14": suggestion.rsi_14,
        "news_sentiment": suggestion.news_sentiment,
        "macro_status": macro_result.status,
        "macro_summary": macro_result.summary,
        "earnings_status": suggestion.earnings_status,
        "fundamentals_status": suggestion.fundamentals_status,
        "missing_domains": suggestion.missing_domains,
        "reasons": suggestion.reasons,
        "criteria": suggestion.criteria_summary,
        "news_headlines": news_result.headlines,
        "news_source_counts": news_result.source_counts,
        "earnings_summary": suggestion.earnings_summary,
        "fundamentals_summary": suggestion.fundamentals_summary,
        "decision_status": suggestion.decision_status,
        "market_data_status": market_data_status,
        "market_data_detail": market_data_detail,
    }


HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8051"))
PID_FILE = Path("data") / "app_dash.pid"


def _is_cloud_runtime() -> bool:
    return bool(
        os.getenv("RENDER")
        or os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("PORT")
    )


def _read_previous_pid() -> int | None:
    if not PID_FILE.exists():
        return None

    try:
        raw = PID_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return int(raw)
    except Exception:
        return None


def _write_current_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup_pid_file() -> None:
    try:
        current_pid = os.getpid()
        tracked_pid = _read_previous_pid()
        if tracked_pid == current_pid and PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        # Cleanup should never block process exit.
        pass


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _terminate_process(pid: int, timeout_seconds: float = 4.0) -> bool:
    if not _is_process_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.1)

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return not _is_process_alive(pid)

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not _is_process_alive(pid):
            return True
        time.sleep(0.1)

    return not _is_process_alive(pid)


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _get_process_name_windows(pid: int) -> str:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return ""

    line = (result.stdout or "").strip()
    if not line or line.startswith("INFO:"):
        return ""

    # CSV format: "Image Name","PID",...
    if line.startswith('"'):
        first = line.split(",", 1)[0]
        return first.strip('"')

    return ""


def _listening_pids_on_port_windows(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return []

    pids: set[int] = set()
    needle = f":{port}"
    for raw_line in (result.stdout or "").splitlines():
        line = raw_line.strip()
        if "LISTENING" not in line or needle not in line:
            continue

        parts = line.split()
        if not parts:
            continue

        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        pids.add(pid)

    return sorted(pids)


def _terminate_stale_port_listeners() -> None:
    current_pid = os.getpid()
    stale_pids = [pid for pid in _listening_pids_on_port_windows(PORT) if pid != current_pid]

    if not stale_pids:
        return

    for pid in stale_pids:
        name = _get_process_name_windows(pid).lower()
        if name and name != "python.exe":
            raise RuntimeError(
                f"GUARDRAIL[PORT_IN_USE_NON_PYTHON] Port {PORT} is occupied by process pid={pid} ({name}). "
                "Stop that process or change PORT before launching."
            )

    print(f"[STARTUP] Found {len(stale_pids)} stale Python listener(s) on port {PORT}. Terminating...")
    for pid in stale_pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)

    deadline = time.time() + 5.0
    while time.time() < deadline:
        remaining = [pid for pid in _listening_pids_on_port_windows(PORT) if pid != current_pid]
        if not remaining:
            return
        time.sleep(0.15)

    remaining = [pid for pid in _listening_pids_on_port_windows(PORT) if pid != current_pid]
    if remaining:
        raise RuntimeError(
            f"GUARDRAIL[STALE_PORT_LISTENER_BLOCKING] Could not clear stale listener(s) on port {PORT}: {remaining}."
        )


def _ensure_fresh_single_instance() -> None:
    _terminate_stale_port_listeners()

    previous_pid = _read_previous_pid()
    current_pid = os.getpid()

    if previous_pid and previous_pid != current_pid and _is_process_alive(previous_pid):
        print(f"[STARTUP] Found existing app session pid={previous_pid}. Terminating stale session...")
        terminated = _terminate_process(previous_pid)
        if not terminated:
            raise RuntimeError(
                f"GUARDRAIL[STALE_SESSION_BLOCKING] Could not terminate stale app session pid={previous_pid}. "
                "Close old app processes and retry."
            )

    if not _is_port_available(HOST, PORT):
        raise RuntimeError(
            f"GUARDRAIL[PORT_ALREADY_IN_USE] Port {PORT} is occupied by another process. "
            "Stop that process or change PORT before launching."
        )

    _write_current_pid()
    atexit.register(_cleanup_pid_file)


def _open_browser_on_start() -> None:
    webbrowser.open_new(f"http://{HOST}:{PORT}/")


app = Dash(__name__)
app.title = "Stock Trend Agent (Dash)"

_initial_claude_status = get_claude_status().get("status_message", "Status unavailable")
APP_SESSION_ID = str(uuid.uuid4())[:8]
APP_STARTED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
INITIAL_WATCHLIST = _load_watchlist() or list(DEFAULT_CONFIG.symbols)

app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.H1("Stock Trend Agent Dashboard", className="title"),
                        html.P(
                            "AI-assisted market signal desk for multi-source news, technicals, and confidence-aware decisions.",
                            className="subtitle",
                        ),
                        html.Div(
                            [
                                html.Span("Trend Intelligence", className="hero-chip"),
                                html.Span("Multi-Source News", className="hero-chip"),
                                html.Span("Guardrail-First", className="hero-chip"),
                            ],
                            className="hero-chip-row",
                        ),
                    ],
                    className="hero-copy",
                ),
                html.Div(
                    [
                        html.Img(
                            src="/assets/market-hero.svg",
                            alt="Abstract stock market candlestick chart art",
                            className="hero-image",
                        ),
                    ],
                    className="hero-visual",
                ),
            ],
            className="hero-shell",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H3("Why This Product Is Useful", className="landing-title"),
                        html.P(
                            "Most investors lose time stitching together charts, headlines, macro signals, and earnings context across multiple tabs.",
                            className="landing-text",
                        ),
                        html.P(
                            "Stock Trend Agent turns that fragmented workflow into one explainable decision surface with confidence and rationale.",
                            className="landing-text",
                        ),
                    ],
                    className="landing-card",
                ),
                html.Div(
                    [
                        html.H3("What Value You Get", className="landing-title"),
                        html.Ul(
                            [
                                html.Li("Faster signal triage across multiple tickers in one run."),
                                html.Li("Transparent decision logic with criteria breakdown and reasons."),
                                html.Li("Higher trust through trusted-source filtering, macro meter, and guardrails."),
                                html.Li("An on-page assistant for quick explanations of trend, risk, and confidence."),
                            ],
                            className="landing-list",
                        ),
                    ],
                    className="landing-card",
                ),
                html.Div(
                    [
                        html.H3("How It Works", className="landing-title"),
                        html.Div(
                            [
                                html.Div([html.Strong("1"), html.Span("Ingest market + news + context streams")], className="landing-step"),
                                html.Div([html.Strong("2"), html.Span("Compute technical, macro, earnings, and fundamentals signals")], className="landing-step"),
                                html.Div([html.Strong("3"), html.Span("Generate confidence-aware decision with explainable rationale")], className="landing-step"),
                            ],
                            className="landing-steps",
                        ),
                    ],
                    className="landing-card",
                ),
                html.Div(
                    [
                        html.A("Start Analyzing", href="#analyzer-start", className="landing-cta-primary"),
                        html.Div(
                            [
                                html.A(
                                    "Run analysis to unlock scorecard",
                                    id="scorecard-jump-link",
                                    href=None,
                                    className="landing-cta-secondary landing-cta-disabled",
                                ),
                                html.Span(
                                    "No analysis results yet. Run Analyze first to populate the scorecard.",
                                    id="scorecard-jump-tooltip",
                                    className="landing-cta-tooltip",
                                ),
                            ],
                            id="scorecard-jump-wrap",
                            className="landing-cta-tooltip-wrap is-disabled",
                        ),
                    ],
                    className="landing-cta-row",
                ),
            ],
            className="landing-shell",
        ),
        html.Div(
            [
                html.Span(f"Session: {APP_SESSION_ID}", style={"fontWeight": "bold"}),
                html.Span(" | ", style={"margin": "0 8px", "color": "#777"}),
                html.Span(f"Started: {APP_STARTED_AT}"),
                html.Span(" | ", style={"margin": "0 8px", "color": "#777"}),
                html.Span(f"Port: {PORT}"),
            ],
            className="card",
            style={"backgroundColor": "#eef6f2", "borderLeft": "4px solid #1a7f64", "fontSize": "14px"},
        ),
        html.Br(),
        html.Div(
            [
                html.H4("Interpretation Guide"),
                html.Ul(
                    [
                        html.Li("Confidence (0.00 to 1.00): composite score from technicals, NLP news, earnings, fundamentals, and guardrails."),
                        html.Li("Confidence >= 0.75: strong alignment; 0.55-0.74: moderate; < 0.55: weak or uncertain setup."),
                        html.Li("RSI(14) < 30: potentially oversold. RSI 30-70: neutral. RSI > 70: potentially overbought."),
                        html.Li("Use confidence and RSI with trend and context streams, not as standalone trade triggers."),
                    ]
                ),
            ],
            className="card guide-card",
        ),
        html.Div(
            [
                html.P("News Filtering Status:", style={"fontWeight": "bold", "marginBottom": "6px"}),
                html.Div(
                    _initial_claude_status,
                    id="claude-status-indicator",
                    style={"fontSize": "14px", "color": "#555"},
                ),
            ],
            className="card",
            style={"backgroundColor": "#f9f7f4", "borderLeft": "4px solid #ff9800"},
        ),
        html.Br(),
        html.H3("Watchlist", className="section-title"),
        html.Div(
            [
                html.Label("My Watchlist (comma separated)"),
                dcc.Input(
                    id="watchlist-input",
                    type="text",
                    value=", ".join(INITIAL_WATCHLIST),
                    className="ticker-input",
                ),
                html.Div(
                    [
                        html.Button("Save Watchlist", id="save-watchlist-button", n_clicks=0, className="analyze-button"),
                        html.Button("Run Daily Signals", id="run-watchlist-signals-button", n_clicks=0, className="analyze-button"),
                    ],
                    className="watchlist-actions",
                ),
                html.Div("Saved watchlist ready.", id="watchlist-status", className="watchlist-status"),
                html.Div(_build_watchlist_chips(INITIAL_WATCHLIST), id="watchlist-current"),
            ],
            className="card",
        ),
        html.Br(),
        html.Div(
            [
                html.H4("Daily Watchlist Signals", style={"marginTop": 0}),
                html.Div(
                    "Trend reversal notifications will appear here after running daily signals.",
                    id="trend-alert-panel",
                    className="trend-alert-panel",
                ),
                dash_table.DataTable(
                    id="daily-signals-table",
                    columns=[],
                    data=[],
                    style_table={"overflowX": "auto", "borderRadius": "12px"},
                    style_cell={"textAlign": "left", "padding": "10px", "maxWidth": 320, "whiteSpace": "normal", "border": "none"},
                    style_header={"fontWeight": "bold", "backgroundColor": "#f1efe8", "border": "none"},
                    style_data={"backgroundColor": "#fffdf8", "border": "none"},
                ),
            ],
            className="card",
        ),
        html.Br(),
        html.Div(
            [
                html.Label("Tickers (comma separated)"),
                dcc.Input(
                    id="ticker-input",
                    type="text",
                    value=", ".join(INITIAL_WATCHLIST),
                    className="ticker-input",
                ),
            ]
        , id="analyzer-start", className="card"),
        html.Br(),
        html.Div(
            [
                html.Label("As of date"),
                dcc.DatePickerSingle(id="asof-date", date=date.today().isoformat()),
                html.Button("Analyze", id="analyze-button", n_clicks=0, className="analyze-button"),
            ]
        , className="card controls-row"),
        html.Br(),
        html.Div(
            [
                html.Label("News Filtering Mode:"),
                dcc.Checklist(
                    id="claude-filter-toggle",
                    options=[
                        {"label": " Use Claude AI for news relevance (24h cache) | OFF = VADER only", "value": "claude_enabled"}
                    ],
                    value=["claude_enabled"],
                    inline=True,
                    style={"display": "inline-block", "marginLeft": "8px"}
                ),
            ]
        , className="card"),
        html.Br(),
        html.Div(id="error-panel", className="error-panel"),
        html.H3("Scorecard", id="scorecard-anchor", className="section-title"),
        dash_table.DataTable(
            id="scorecard-table",
            columns=[],
            data=[],
            style_table={"overflowX": "auto", "borderRadius": "12px"},
            style_cell={"textAlign": "left", "padding": "10px", "maxWidth": 260, "whiteSpace": "normal", "border": "none"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f1efe8", "border": "none"},
            style_data={"backgroundColor": "#fffdf8", "border": "none"},
            style_data_conditional=[
                {
                    "if": {"filter_query": '{trend_display} contains "UP"', "column_id": "trend_display"},
                    "color": "#0d7f5f",
                    "fontWeight": "700",
                },
                {
                    "if": {"filter_query": '{trend_display} contains "DOWN"', "column_id": "trend_display"},
                    "color": "#c0392b",
                    "fontWeight": "700",
                },
                {
                    "if": {"filter_query": '{trend_display} contains "NEUTRAL"', "column_id": "trend_display"},
                    "color": "#6c7685",
                    "fontWeight": "700",
                },
            ],
        ),
        html.H3("Rationale", className="section-title"),
        html.Div(id="rationale-panel"),
        # Chat bubble and modal
        html.Button(
            html.Span("💬", style={"fontSize": "24px"}),
            id="chat-bubble-button",
            className="chat-bubble",
            title="Ask about macro tone, risk, technicals, or analysis",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [
                                html.H4("Analysis Assistant", style={"margin": 0, "cursor": "grab"}, id="chat-modal-header"),
                                html.Button("✕", id="close-chat-button", className="close-button"),
                            ],
                            style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px", "userSelect": "none"},
                        ),
                        html.Div(
                            id="chat-messages-container",
                            style={
                                "height": "300px",
                                "overflowY": "auto",
                                "border": "1px solid #ddd",
                                "borderRadius": "8px",
                                "padding": "12px",
                                "marginBottom": "12px",
                                "backgroundColor": "#f9f9f9",
                            },
                        ),
                        html.Div(
                            [
                                html.P("Example questions:", style={"fontSize": "12px", "color": "#666", "marginBottom": "8px"}),
                                html.Div(
                                    [
                                        html.Button(
                                            question,
                                            id={"type": "example-question", "index": i},
                                            className="example-question-button",
                                        )
                                        for i, question in enumerate(EXAMPLE_QUESTIONS[:3])
                                    ],
                                    style={"display": "flex", "flexDirection": "column", "gap": "6px", "marginBottom": "12px"},
                                ),
                            ],
                            style={"marginBottom": "12px"},
                        ),
                        html.Div(
                            [
                                dcc.Input(
                                    id="chat-input",
                                    type="text",
                                    placeholder="Ask about macro tone, RSI, risk adjustment...",
                                    className="chat-input",
                                ),
                                html.Button("Send", id="send-chat-button", className="send-button"),
                            ],
                            style={"display": "flex", "gap": "8px"},
                        ),
                        html.P(
                            "Tip: pick a suggestion or type a question, then press Send to ask it.",
                            style={"fontSize": "12px", "color": "#6b7280", "margin": "6px 0 0"},
                        ),
                        html.Div(
                            id="chat-question-counter",
                            style={"fontSize": "12px", "color": "#999", "marginTop": "8px", "textAlign": "right"},
                        ),
                    ],
                    style={"padding": "16px"},
                ),
            ],
            id="chat-modal-container",
            className="chat-modal-floating",
            style={"display": "none"},
        ),
        # Store for chat state
        dcc.Store(id="chat-messages-store", data=[]),
        dcc.Store(id="chat-context-store", data={}),
        dcc.Store(id="chat-question-count-store", data=0),
        dcc.Interval(id="status-refresh-interval", interval=30000, n_intervals=0),  # Refresh every 30s
    ],
    className="page-shell",
)


@app.callback(
    Output("scorecard-table", "columns"),
    Output("scorecard-table", "data"),
    Output("rationale-panel", "children"),
    Output("error-panel", "children"),
    Input("analyze-button", "n_clicks"),
    State("ticker-input", "value"),
    State("asof-date", "date"),
    State("claude-filter-toggle", "value"),
)
def run_analysis(n_clicks: int, ticker_text: str, asof_date_value: str, claude_filter_value: list):
    if not n_clicks:
        return [], [], [], html.Div("Enter tickers and click Analyze.")

    use_claude_filter = "claude_enabled" in (claude_filter_value or [])

    as_of_date = date.fromisoformat(asof_date_value)
    tickers = _parse_tickers(ticker_text or "")

    try:
        _validate_request(tickers=tickers, as_of_date=as_of_date)
    except GuardrailError as exc:
        return [], [], [], html.Div(str(exc), style={"color": "#b00020", "fontWeight": "bold"})

    results: list[dict] = []
    failures: list[tuple[str, str]] = []

    for ticker in tickers:
        try:
            results.append(analyze_symbol(symbol=ticker, as_of_date=as_of_date, use_claude_filter=use_claude_filter))
        except GuardrailError as exc:
            failures.append((ticker, str(exc)))
        except Exception as exc:
            failures.append((ticker, f"GUARDRAIL[UNEXPECTED_ERROR] Unexpected analysis failure: {exc}"))

    columns = [
        {"name": "Symbol", "id": "symbol"},
        {"name": "Trend", "id": "trend_display"},
        {"name": "Final Decision", "id": "final_decision"},
        {"name": "Technical Signal", "id": "technical_signal"},
        {"name": "Confidence", "id": "confidence"},
        {"name": "RSI(14)", "id": "rsi_14"},
        {"name": "News", "id": "news_sentiment"},
        {"name": "Market Data", "id": "market_data_status"},
        {"name": "Macro", "id": "macro_status"},
        {"name": "Earnings", "id": "earnings_status"},
        {"name": "Fundamentals", "id": "fundamentals_status"},
        {"name": "Missing Domains", "id": "missing_domains_text"},
    ]

    table_data = [
        {
            "symbol": row["symbol"],
            "trend_display": _format_trend_badge(row["trend"]),
            "final_decision": row["final_decision"],
            "technical_signal": row["technical_signal"],
            "confidence": f"{row['confidence']:.2f}",
            "rsi_14": f"{row['rsi_14']:.2f}",
            "news_sentiment": row["news_sentiment"],
            "market_data_status": _format_market_data_badge(row.get("market_data_status", "unknown")),
            "macro_status": row["macro_status"],
            "earnings_status": row["earnings_status"],
            "fundamentals_status": row["fundamentals_status"],
            "missing_domains_text": ", ".join(row["missing_domains"]),
        }
        for row in results
    ]

    rationale_children = []
    for row in results:
        reason_items = [html.Li(reason) for reason in row["reasons"]]
        headline_items = [html.Li(headline) for headline in row["news_headlines"][:3]]
        source_counts = row.get("news_source_counts", {}) or {}
        source_items = [
            html.Li(f"{source}: {count}")
            for source, count in sorted(source_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        criteria_sections = _parse_criteria_sections(row.get("criteria", ""))
        macro_label, macro_details, macro_meter = _macro_meter_payload(
            row.get("macro_status", ""),
            row.get("macro_summary", ""),
        )

        criteria_cards = []
        if criteria_sections["technical"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Technical Setup"),
                        html.P(criteria_sections["technical"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-technical",
                )
            )

        if criteria_sections["risk"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Risk Adjustment"),
                        html.P(criteria_sections["risk"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-risk",
                )
            )

        if criteria_sections["news"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("News Effect"),
                        html.P(criteria_sections["news"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-news",
                )
            )

        if criteria_sections["earnings"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Earnings Context"),
                        html.P(criteria_sections["earnings"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-earnings",
                )
            )

        if criteria_sections["fundamentals"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Fundamentals Context"),
                        html.P(criteria_sections["fundamentals"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-fundamentals",
                )
            )

        if criteria_sections["gating"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Conviction Gate"),
                        html.P(criteria_sections["gating"], className="criteria-text"),
                    ],
                    className="criteria-card criteria-gating",
                )
            )

        for piece in criteria_sections["other"]:
            criteria_cards.append(
                html.Div(
                    [
                        html.Strong("Additional Rule"),
                        html.P(piece, className="criteria-text"),
                    ],
                    className="criteria-card",
                )
            )

        rationale_children.append(
            html.Details(
                [
                    html.Summary(f"{row['symbol']} - {row['final_decision']}", style={"fontWeight": "bold"}),
                    html.P(f"Trend: {row['trend']} | Confidence: {row['confidence']:.2f} | RSI(14): {row['rsi_14']:.2f}"),
                    html.P(f"Decision Status: {row['decision_status']}"),
                    html.P(
                        [
                            "Market Data Status: ",
                            html.Span(
                                _format_market_data_badge(row.get("market_data_status", "unknown")),
                                className=f"market-data-badge market-data-{row.get('market_data_status', 'unknown')}"
                            ),
                        ]
                    ),
                    html.P(row.get("market_data_detail", "Market data source detail unavailable.")),
                    html.P("Macro Meter:"),
                    html.Div(
                        [
                            html.Div(
                                html.Div(className="macro-meter-fill", style={"width": f"{macro_meter}%"}),
                                className="macro-meter-track",
                            ),
                            html.Div(
                                [
                                    html.Strong(f"Macro Tone: {macro_label}"),
                                    html.P(macro_details, className="criteria-text"),
                                ],
                                className="macro-meter-caption",
                            ),
                        ],
                        className="macro-meter-shell",
                    ),
                    html.P("Criteria Breakdown:"),
                    html.Div(criteria_cards, className="criteria-grid") if criteria_cards else html.P("No criteria details available"),
                    html.P("Reasons:"),
                    html.Ul(reason_items),
                    html.P("News Headlines:"),
                    html.Ul(headline_items) if headline_items else html.P("No trusted headlines available"),
                    html.P("News Sources Used:"),
                    html.Ul(source_items) if source_items else html.P("No relevant news sources found"),
                    html.P(f"Earnings Context: {row['earnings_summary']}"),
                    html.P(f"Fundamentals Context: {row['fundamentals_summary']}"),
                ],
                style={"border": "1px solid #ddd", "padding": "8px", "marginBottom": "8px"},
            )
        )

    error_children = []
    if failures:
        error_children = [
            html.Div(f"{ticker}: {message}", style={"color": "#b00020", "marginBottom": "6px"})
            for ticker, message in failures
        ]

    return columns, table_data, rationale_children, error_children


@app.callback(
    Output("watchlist-status", "children"),
    Output("watchlist-current", "children"),
    Output("watchlist-input", "value"),
    Output("ticker-input", "value"),
    Input("save-watchlist-button", "n_clicks"),
    State("watchlist-input", "value"),
    prevent_initial_call=True,
)
def save_watchlist(n_clicks: int, watchlist_text: str):
    del n_clicks
    symbols = _parse_tickers(watchlist_text or "")
    deduped: list[str] = []
    for symbol in symbols:
        if symbol not in deduped:
            deduped.append(symbol)

    if not deduped:
        status = html.Span("Watchlist is empty. Add at least one ticker.", style={"color": "#b00020", "fontWeight": "bold"})
        return status, _build_watchlist_chips([]), "", ""

    if len(deduped) > MAX_WATCHLIST_SIZE:
        status = html.Span(
            f"Watchlist exceeds limit ({MAX_WATCHLIST_SIZE}). Reduce symbols and try again.",
            style={"color": "#b00020", "fontWeight": "bold"},
        )
        return status, _build_watchlist_chips(deduped), ", ".join(deduped), ", ".join(deduped)

    try:
        for symbol in deduped:
            _validate_ticker_symbol(symbol)
    except GuardrailError as exc:
        status = html.Span(str(exc), style={"color": "#b00020", "fontWeight": "bold"})
        return status, _build_watchlist_chips(deduped), ", ".join(deduped), ", ".join(deduped)

    _save_watchlist(deduped)
    status = html.Span(
        f"Watchlist saved ({len(deduped)} symbols).",
        style={"color": "#0d7f5f", "fontWeight": "bold"},
    )
    normalized = ", ".join(deduped)
    return status, _build_watchlist_chips(deduped), normalized, normalized


@app.callback(
    Output("daily-signals-table", "columns"),
    Output("daily-signals-table", "data"),
    Output("trend-alert-panel", "children"),
    Input("run-watchlist-signals-button", "n_clicks"),
    State("watchlist-input", "value"),
    State("asof-date", "date"),
    State("claude-filter-toggle", "value"),
    prevent_initial_call=True,
)
def run_watchlist_daily_signals(n_clicks: int, watchlist_text: str, asof_date_value: str, claude_filter_value: list):
    if not n_clicks:
        raise Exception("Cancelled")

    tickers = _parse_tickers(watchlist_text or "")
    as_of_date = date.fromisoformat(asof_date_value)
    use_claude_filter = "claude_enabled" in (claude_filter_value or [])

    try:
        _validate_request(tickers=tickers, as_of_date=as_of_date)
    except GuardrailError as exc:
        return [], [], html.Div(str(exc), className="trend-alert trend-alert-error")

    results: list[dict] = []
    failures: list[str] = []
    for symbol in tickers:
        try:
            results.append(analyze_symbol(symbol=symbol, as_of_date=as_of_date, use_claude_filter=use_claude_filter))
        except Exception as exc:
            failures.append(f"{symbol}: {exc}")

    columns = [
        {"name": "Symbol", "id": "symbol"},
        {"name": "Trend", "id": "trend_display"},
        {"name": "Decision", "id": "final_decision"},
        {"name": "Confidence", "id": "confidence"},
        {"name": "Explainable Reason", "id": "reason"},
        {"name": "Trusted Headlines", "id": "headlines"},
    ]

    rows = []
    for row in results:
        reason = row.get("reasons", ["No reason generated"])[:1]
        headlines = row.get("news_headlines", [])[:2]
        rows.append(
            {
                "symbol": row["symbol"],
                "trend_display": _format_trend_badge(row["trend"]),
                "trend": row["trend"],
                "final_decision": row["final_decision"],
                "confidence": f"{row['confidence']:.2f}",
                "reason": reason[0] if reason else "No reason generated",
                "headlines": " | ".join(headlines) if headlines else "No trusted headlines available",
            }
        )

    previous_trends = _get_previous_trends(as_of_date=as_of_date)
    alerts: list[str] = []
    for row in rows:
        symbol = row["symbol"]
        current = str(row.get("trend", "")).lower()
        previous = str(previous_trends.get(symbol, "")).lower()
        if previous in {"uptrend", "downtrend"} and current in {"uptrend", "downtrend"} and previous != current:
            alerts.append(f"Trend reversal for {symbol}: {previous} -> {current}")

    if rows:
        _upsert_daily_signal_run(as_of_date=as_of_date, analyzed_rows=rows)

    alert_nodes = []
    if alerts:
        alert_nodes.extend([html.Div(msg, className="trend-alert trend-alert-warning") for msg in alerts])
    else:
        alert_nodes.append(html.Div("No trend reversal alerts for this run.", className="trend-alert trend-alert-ok"))

    if failures:
        alert_nodes.extend([html.Div(msg, className="trend-alert trend-alert-error") for msg in failures])

    # Do not expose raw trend helper column in table.
    cleaned_rows = [{k: v for k, v in row.items() if k != "trend"} for row in rows]
    return columns, cleaned_rows, alert_nodes


@app.callback(
    Output("scorecard-jump-link", "href"),
    Output("scorecard-jump-link", "className"),
    Output("scorecard-jump-link", "children"),
    Output("scorecard-jump-wrap", "className"),
    Output("scorecard-jump-tooltip", "className"),
    Output("scorecard-jump-tooltip", "children"),
    Input("scorecard-table", "data"),
)
def toggle_scorecard_jump_link(scorecard_rows: list[dict] | None):
    has_rows = bool(scorecard_rows)
    if has_rows:
        return (
            "#scorecard-anchor",
            "landing-cta-secondary",
            "Jump To Scorecard",
            "landing-cta-tooltip-wrap",
            "landing-cta-tooltip",
            "",
        )

    return (
        None,
        "landing-cta-secondary landing-cta-disabled",
        "Run analysis to unlock scorecard",
        "landing-cta-tooltip-wrap is-disabled",
        "landing-cta-tooltip",
        "No analysis results yet. Run Analyze first to populate the scorecard.",
    )


@app.callback(
    Output("chat-modal-container", "style"),
    Input("chat-bubble-button", "n_clicks"),
    Input("close-chat-button", "n_clicks"),
    State("chat-modal-container", "style"),
)
def toggle_chat_modal(bubble_clicks: int, close_clicks: int, current_style: dict):
    """Toggle chat modal visibility."""
    if not (bubble_clicks or close_clicks):
        return current_style or {"display": "none"}
    
    current_display = (current_style or {}).get("display", "none")
    new_display = "none" if current_display != "none" else "block"
    
    return {"display": new_display}


@app.callback(
    Output("chat-input", "value"),
    Input({"type": "example-question", "index": ALL}, "n_clicks"),
    State({"type": "example-question", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def populate_from_example_question(clicks, button_ids):
    """Populate input field when example question button is clicked."""
    from dash import callback_context
    
    triggered_id = callback_context.triggered_id
    if not triggered_id:
        raise Exception("Cancelled")

    if isinstance(triggered_id, dict):
        idx = triggered_id.get("index", -1)
        if 0 <= idx < len(EXAMPLE_QUESTIONS):
            return EXAMPLE_QUESTIONS[idx]

    # Fallback for older Dash event payloads
    for index, button_id_obj in enumerate(button_ids or []):
        if isinstance(button_id_obj, dict) and button_id_obj.get("index") == triggered_id:
            if 0 <= index < len(EXAMPLE_QUESTIONS):
                return EXAMPLE_QUESTIONS[index]

    raise Exception("Cancelled")


@app.callback(
    Output("chat-messages-store", "data"),
    Output("chat-question-count-store", "data"),
    Output("chat-messages-container", "children"),
    Output("chat-question-counter", "children"),
    Output("chat-input", "value", allow_duplicate=True),
    Input("send-chat-button", "n_clicks"),
    State("chat-input", "value"),
    State("chat-messages-store", "data"),
    State("chat-question-count-store", "data"),
    State("chat-context-store", "data"),
    prevent_initial_call=True,
)
def send_chat_message(send_clicks: int, input_value: str, messages: list, question_count: int, context: dict):
    """Handle sending a chat message (works with or without analysis context)."""
    question_to_ask = (input_value or "").strip()
    
    if not question_to_ask:
        raise Exception("Cancelled")
    
    max_q = DEFAULT_CONFIG.max_questions_per_session
    
    # Check question limit
    if question_count >= max_q:
        error_msg = f"Question limit ({max_q}) reached this session. Please refresh the page to continue."
        messages.append({"role": "assistant", "text": error_msg, "error": True})
        msg_children = _render_chat_messages(messages)
        counter_text = f"Questions: {question_count}/{max_q} (limit reached)"
        return messages, question_count, msg_children, counter_text, ""
    
    # Add user message
    messages.append({"role": "user", "text": question_to_ask})
    
    # Get response from chat agent (works even without context for general questions)
    context = context or {}
    if not context.get("symbol"):
        context = _build_question_context_from_ticker(
            question=question_to_ask,
            as_of_date=date.today(),
            use_claude_filter=True,
        ) or context

    response = answer_question(
        question=question_to_ask,
        symbol=context.get("symbol"),
        final_decision=context.get("final_decision"),
        confidence=float(context.get("confidence", 0.0)) if context.get("confidence") is not None else None,
        trend=context.get("trend"),
        rsi_14=float(context.get("rsi_14", 0.0)) if context.get("rsi_14") is not None else None,
        technical_signal=context.get("technical_signal"),
        criteria_summary=context.get("criteria"),
        macro_tone=context.get("macro_tone"),
        macro_summary=context.get("macro_summary"),
        news_sentiment=context.get("news_sentiment"),
        earnings_summary=context.get("earnings_summary"),
        fundamentals_summary=context.get("fundamentals_summary"),
        questions_asked=question_count,
        max_questions=max_q,
    )
    
    # Add assistant message
    messages.append({
        "role": "assistant",
        "text": response.message,
        "error": not response.success,
    })
    
    # Update question count
    new_question_count = question_count + 1
    
    # Render messages
    msg_children = _render_chat_messages(messages)
    counter_text = f"Questions: {new_question_count}/{max_q}"
    
    return messages, new_question_count, msg_children, counter_text, ""


def _render_chat_messages(messages: list) -> list:
    """Render chat messages for display."""
    children = []
    for msg in messages:
        role_class = "assistant" if msg["role"] == "assistant" else "user"
        error_class = " error" if msg.get("error", False) else ""
        children.append(
            html.Div(
                msg["text"],
                className=f"chat-message {role_class}{error_class}",
            )
        )
    return children


@app.callback(
    Output("chat-context-store", "data"),
    Input("analyze-button", "n_clicks"),
    State("ticker-input", "value"),
    State("asof-date", "date"),
    State("claude-filter-toggle", "value"),
    prevent_initial_call=True,
)
def update_chat_context(n_clicks: int, ticker_text: str, asof_date_value: str, claude_filter_value: list):
    """Update chat context when analysis is run (store latest analysis data)."""
    if not n_clicks:
        raise Exception("Cancelled")
    
    use_claude_filter = "claude_enabled" in (claude_filter_value or [])
    as_of_date = date.fromisoformat(asof_date_value)
    tickers = _parse_tickers(ticker_text or "")
    
    if not tickers:
        return {}
    
    # Get the first ticker's analysis (for now, store just one context)
    try:
        result = analyze_symbol(symbol=tickers[0], as_of_date=as_of_date, use_claude_filter=use_claude_filter)
        
        macro_label, _, _ = _macro_meter_payload(result.get("macro_status", ""), result.get("macro_summary", ""))
        
        return {
            "symbol": result["symbol"],
            "final_decision": result["final_decision"],
            "confidence": result["confidence"],
            "trend": result["trend"],
            "rsi_14": result["rsi_14"],
            "technical_signal": result["technical_signal"],
            "criteria": result["criteria"],
            "macro_tone": macro_label,
            "macro_summary": result["macro_summary"],
            "news_sentiment": result["news_sentiment"],
            "earnings_summary": result["earnings_summary"],
            "fundamentals_summary": result["fundamentals_summary"],
        }
    except Exception:
        return {}
    """Update Claude status indicator every 30s or after analysis."""
    status = get_claude_status()
    
    # Build the status display
    if status["claude_available"]:
        indicator = html.Div(
            [
                html.Span(
                    f"✅ {status['status_message']}",
                    style={"color": "#4caf50", "fontWeight": "bold"}
                ),
            ]
        )
    else:
        indicator = html.Div(
            [
                html.Span(
                    status['status_message'],
                    style={"color": "#f57c00", "fontWeight": "bold"}
                ),
                html.Br(),
                html.Span(
                    "To enable Claude: set ANTHROPIC_API_KEY in Render Environment or local .env, then restart/redeploy",
                    style={"fontSize": "12px", "color": "#999", "fontStyle": "italic"}
                ),
            ]
        )
    
    return indicator


if __name__ == "__main__":
    if not _is_cloud_runtime():
        _ensure_fresh_single_instance()
        threading.Timer(0.8, _open_browser_on_start).start()
    app.run(host=HOST, port=PORT, debug=False)
