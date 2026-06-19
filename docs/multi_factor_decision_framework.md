# Multi-Factor Decision Framework

## Why RSI Alone Is Not Enough
A money-impacting decision should not rely on one indicator or even technicals alone. RSI can help identify momentum and overbought/oversold conditions, but it does not capture:
- Earnings surprises and guidance
- Company-specific news
- Economic and macro regime changes
- Fundamental valuation and growth quality
- Event risk around reports, product launches, regulation, or litigation

## Required Evidence Domains For Final Conviction
The project should treat a buy/sell-style call as final only when all of these are available:
- technicals
- macro_news
- earnings
- fundamentals
- company_news

## Current Enforcement
- The current pipeline includes technicals, company news, earnings, fundamentals, and lightweight macro news.
- Strict full-context gating is currently set to disabled by default in config for faster iteration.
- If strict gating is enabled, directional outcomes are labeled as Preliminary Bullish / Preliminary Bearish when required domains are missing.

## In-App Explanation Layer
- The dashboard includes a floating Analysis Assistant for explaining the current analysis.
- The assistant accepts general questions, ticker-aware prompts, and short prompts like a ticker symbol plus a trend question.
- If a ticker is mentioned in the prompt, the app attempts to build fresh analysis context for that symbol before answering.
- The assistant can separate question intent between:
	- current-analysis interpretation (use current page metrics)
	- general ticker/company information (overview mode)
	- general concept education (metric definitions)
- The assistant is meant to explain the current decision framework, not replace it.

## Recommended Final Decision Stack
1. Technical signals
2. Earnings context
3. Company news and sentiment
4. Macro/economic context
5. Fundamentals and valuation
6. Risk overlay
7. Critic or challenger review

## Output Philosophy
Each ticker should ultimately produce:
- final_decision
- technical_signal
- confidence
- missing_domains
- rationale
- risk_flags

## Build Order
1. Refine macro-news quality and add richer macro regime features
2. Add evaluation and walk-forward testing
3. Add explainability overlays in dashboard and report outputs
4. Add interactive chart layer and model diagnostics
5. Improve assistant guardrails, conversation memory, and contextual ticker resolution
