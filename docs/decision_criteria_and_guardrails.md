# Decision Criteria and Data Source Guardrails

## Suggestion Criteria (Current Baseline)

### Strong Buy
A ticker is tagged Strong Buy only if all conditions are true:
- Trend state is Uptrend.
- RSI(14) is between 55 and 68.
- 5-day momentum is at least +2%.
- ATR(14)/Close is at most 3.5%.

Interpretation:
- Trend is positive, momentum is confirmed, RSI is strong but not overbought, and volatility is controlled.

### Watch Buy
- Trend is Uptrend.
- 5-day momentum is positive.
- RSI(14) is 72 or below.

### Hold
Typical Hold cases:
- Uptrend exists but RSI(14) is above 72 (overbought guardrail).
- No clear edge despite partial positive signals.

### Reduce Risk
- Trend is Downtrend.
- 5-day momentum is negative.

### No Action
- Signals are mixed (Neutral trend state).

### Preliminary Bullish / Preliminary Bearish (Strict Gating Mode)
- When strict full-context enforcement is enabled and required evidence domains are missing:
  - Strong Buy / Watch Buy become Preliminary Bullish.
  - Reduce Risk becomes Preliminary Bearish.
- Confidence is capped and final conviction remains blocked until missing domains are available.

## RSI Guardrail
- RSI > 72 prevents Strong Buy and pushes recommendation toward Hold.
- This reduces chasing overextended moves.

## Volatility Guardrail
- If ATR/Close > 4%, confidence gets a penalty (-0.10).

## Trusted Data Source Guardrail
- The pipeline enforces an allowlist of trusted providers.
- Current allowlist includes trusted finance/news domains (yfinance, Reuters, Bloomberg, WSJ, CNBC, MarketWatch, and related feed hosts).
- Any non-allowlisted source raises an error and blocks execution.

## Dashboard Explanation Guardrails
- The Analysis Assistant is allowed to answer short prompts, ticker-only prompts, and general questions about the metrics shown on the page.
- If a ticker is mentioned in the question, the assistant attempts to resolve it and explain the current analysis for that ticker even if the user did not analyze it first.
- If dashboard analysis context already exists, the assistant still distinguishes intent:
  - analysis-context questions use current page metrics and decision context
  - general-ticker questions provide company-level overview rather than only current page context
- Example questions in the UI populate the input field only; the user must press Send to submit the question.
- The chat window opens as a floating, draggable panel so it does not block the main dashboard workflow.

## News Availability Guardrail
- If live company news retrieval fails, the system may reuse trusted cached company articles from the last 15 days.
- If no trusted recent cache exists, company-news status remains unavailable and confidence logic follows missing-domain behavior.

Implemented in:
- src/config.py
- src/data_ingestion.py

## Compliance Intent
- Decision support only, not financial advice.
- Transparent criteria are included in each daily report row.
