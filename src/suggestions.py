from __future__ import annotations

from dataclasses import dataclass

from src.trend import TrendResult


@dataclass(frozen=True)
class SuggestionResult:
    suggestion: str
    confidence: float
    rsi_14: float
    reasons: list[str]
    criteria_summary: str
    technical_signal: str
    decision_status: str
    missing_domains: list[str]
    news_sentiment: str
    news_status: str
    earnings_status: str
    earnings_summary: str
    fundamentals_status: str
    fundamentals_summary: str


def make_suggestion(
    trend: TrendResult,
    atr_ratio: float,
    momentum_5: float,
    rsi_14: float,
    news_sentiment: str,
    news_confidence_delta: float,
    news_reasons: list[str],
    news_status: str,
    earnings_confidence_delta: float,
    earnings_reasons: list[str],
    earnings_status: str,
    earnings_summary: str,
    fundamentals_confidence_delta: float,
    fundamentals_reasons: list[str],
    fundamentals_status: str,
    fundamentals_summary: str,
    macro_confidence_delta: float,
    macro_reasons: list[str],
    macro_status: str,
    macro_summary: str,
    available_domains: tuple[str, ...],
    required_domains: tuple[str, ...],
    enforce_full_context: bool,
) -> SuggestionResult:
    reasons = list(trend.evidence)
    criteria_summary = ""
    decision_status = "final"
    missing_domains = [domain for domain in required_domains if domain not in available_domains]

    strong_buy = (
        trend.trend_state == "Uptrend"
        and 55 <= rsi_14 <= 68
        and momentum_5 >= 0.02
        and atr_ratio <= 0.035
    )

    hold_on_overbought = trend.trend_state == "Uptrend" and rsi_14 > 72
    technical_signal = "Hold"

    if strong_buy:
        technical_signal = "Strong Buy"
        suggestion = technical_signal
        confidence = 0.82
        reasons.extend([
            "rsi_55_to_68_strength_zone",
            "momentum_5d_above_2pct",
            "controlled_volatility",
        ])
        criteria_summary = "Uptrend + RSI 55-68 + 5d momentum >= 2% + ATR/Close <= 3.5%"
    elif trend.trend_state == "Uptrend" and momentum_5 > 0 and rsi_14 <= 72:
        technical_signal = "Watch Buy"
        suggestion = technical_signal
        confidence = 0.7
        reasons.append("positive_5d_momentum")
        criteria_summary = "Uptrend + positive momentum + RSI <= 72"
    elif hold_on_overbought:
        technical_signal = "Hold"
        suggestion = technical_signal
        confidence = 0.62
        reasons.append("rsi_above_72_overbought_guardrail")
        criteria_summary = "Uptrend but RSI > 72 suggests overbought risk"
    elif trend.trend_state == "Downtrend" and momentum_5 < 0:
        technical_signal = "Reduce Risk"
        suggestion = technical_signal
        confidence = 0.72
        reasons.append("negative_5d_momentum")
        criteria_summary = "Downtrend + negative momentum"
    elif trend.trend_state == "Neutral":
        technical_signal = "No Action"
        suggestion = technical_signal
        confidence = 0.55
        criteria_summary = "Mixed technical signals"
    else:
        technical_signal = "Hold"
        suggestion = technical_signal
        confidence = 0.6
        criteria_summary = "No strong directional edge"

    if atr_ratio > 0.04:
        confidence = max(0.0, confidence - 0.1)
        reasons.append("volatility_penalty")

        if criteria_summary:
            criteria_summary += "; confidence penalty for ATR/Close > 4%"

    if news_status == "trusted_news_available":
        confidence = min(0.95, max(0.0, confidence + news_confidence_delta))
        reasons.extend(news_reasons)

        if news_sentiment == "negative" and technical_signal in {"Strong Buy", "Watch Buy"}:
            suggestion = "Hold"
            criteria_summary += "; negative trusted company news overrode bullish technical setup"
        elif news_sentiment == "positive" and technical_signal == "Hold":
            criteria_summary += "; positive trusted company news supports hold bias"
        elif news_sentiment == "neutral":
            criteria_summary += "; trusted company news is neutral"

    if earnings_status == "earnings_data_available":
        confidence = min(0.95, max(0.0, confidence + earnings_confidence_delta))
        reasons.extend(earnings_reasons)
        criteria_summary += f"; earnings context: {earnings_summary}"

    if fundamentals_status == "fundamentals_data_available":
        confidence = min(0.95, max(0.0, confidence + fundamentals_confidence_delta))
        reasons.extend(fundamentals_reasons)
        criteria_summary += f"; fundamentals context: {fundamentals_summary}"

    if macro_status == "macro_news_available":
        confidence = min(0.95, max(0.0, confidence + macro_confidence_delta))
        reasons.extend(macro_reasons)
        criteria_summary += f"; macro context: {macro_summary}"

    if enforce_full_context and missing_domains:
        decision_status = "technical_preliminary"
        reasons.append("missing_required_nontechnical_context")
        confidence = min(confidence, 0.5)

        if technical_signal in {"Strong Buy", "Watch Buy"}:
            suggestion = "Preliminary Bullish"
        elif technical_signal == "Reduce Risk":
            suggestion = "Preliminary Bearish"
        else:
            suggestion = technical_signal

        missing_text = ", ".join(missing_domains)
        criteria_summary += (
            f"; final conviction disabled until missing context is available: {missing_text}"
        )

    return SuggestionResult(
        suggestion=suggestion,
        confidence=round(confidence, 2),
        rsi_14=round(rsi_14, 2),
        reasons=reasons[:3],
        criteria_summary=criteria_summary,
        technical_signal=technical_signal,
        decision_status=decision_status,
        missing_domains=missing_domains,
        news_sentiment=news_sentiment,
        news_status=news_status,
        earnings_status=earnings_status,
        earnings_summary=earnings_summary,
        fundamentals_status=fundamentals_status,
        fundamentals_summary=fundamentals_summary,
    )
