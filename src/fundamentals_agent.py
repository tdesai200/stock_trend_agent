from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass(frozen=True)
class FundamentalsAgentResult:
    status: str
    confidence_delta: float
    reasons: list[str]
    summary: str
    pe_ratio: float | None
    profit_margin: float | None
    revenue_growth: float | None
    debt_to_equity: float | None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_fundamentals_signal(symbol: str, source: str) -> FundamentalsAgentResult:
    if source != "yfinance":
        raise ValueError(f"Untrusted or unsupported fundamentals source={source}")

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        return FundamentalsAgentResult(
            status="no_fundamentals_data",
            confidence_delta=0.0,
            reasons=["fundamentals_fetch_failed"],
            summary="No trusted fundamentals context available",
            pe_ratio=None,
            profit_margin=None,
            revenue_growth=None,
            debt_to_equity=None,
        )

    pe_ratio = _to_float(info.get("trailingPE") or info.get("forwardPE"))
    profit_margin = _to_float(info.get("profitMargins"))
    revenue_growth = _to_float(info.get("revenueGrowth"))
    debt_to_equity = _to_float(info.get("debtToEquity"))

    if (
        pe_ratio is None
        and profit_margin is None
        and revenue_growth is None
        and debt_to_equity is None
    ):
        return FundamentalsAgentResult(
            status="no_fundamentals_data",
            confidence_delta=0.0,
            reasons=["no_fundamentals_context"],
            summary="No trusted fundamentals context available",
            pe_ratio=None,
            profit_margin=None,
            revenue_growth=None,
            debt_to_equity=None,
        )

    confidence_delta = 0.0
    reasons: list[str] = []

    if profit_margin is not None:
        if profit_margin >= 0.20:
            confidence_delta += 0.04
            reasons.append("fundamentals_margin_strong")
        elif profit_margin <= 0.05:
            confidence_delta -= 0.04
            reasons.append("fundamentals_margin_weak")

    if revenue_growth is not None:
        if revenue_growth >= 0.10:
            confidence_delta += 0.05
            reasons.append("fundamentals_growth_strong")
        elif revenue_growth <= 0.0:
            confidence_delta -= 0.05
            reasons.append("fundamentals_growth_weak")

    if debt_to_equity is not None:
        if debt_to_equity >= 200:
            confidence_delta -= 0.03
            reasons.append("fundamentals_leverage_high")
        elif debt_to_equity <= 50:
            confidence_delta += 0.02
            reasons.append("fundamentals_leverage_prudent")

    if pe_ratio is not None and pe_ratio >= 45:
        confidence_delta -= 0.02
        reasons.append("fundamentals_valuation_rich")

    summary = (
        f"pe={pe_ratio if pe_ratio is not None else 'unknown'}, "
        f"margin={profit_margin if profit_margin is not None else 'unknown'}, "
        f"revenue_growth={revenue_growth if revenue_growth is not None else 'unknown'}, "
        f"debt_to_equity={debt_to_equity if debt_to_equity is not None else 'unknown'}"
    )

    return FundamentalsAgentResult(
        status="fundamentals_data_available",
        confidence_delta=round(confidence_delta, 3),
        reasons=reasons or ["fundamentals_context_available"],
        summary=summary,
        pe_ratio=pe_ratio,
        profit_margin=profit_margin,
        revenue_growth=revenue_growth,
        debt_to_equity=debt_to_equity,
    )