# Stock Trend Agent

Daily stock trend assistant that generates suggestions with transparent rationale and confidence, designed to evolve into a multi-agent dashboard with an in-app analysis assistant.

## Product Direction
Target user flow over the next phases:
- Week 1: Python script + command-line output
- Week 2: Dash dashboard
- Week 3: Interactive charts

Example future interaction:
- You: Analyze NVDA
- Agent: Trend: Bullish, RSI: 61, Score: 3/3, Recommendation: Continue monitoring momentum.

## Week 1 Objective
Ship an MVP that runs daily for a small ticker universe and produces a markdown report with trend + suggestion + reasons.

## Current Structure
- data/: raw and processed snapshots
- reports/: generated daily reports and evaluation outputs
- src/: source code
- docs/: project planning and agent contracts

## Setup
1. Create and activate a Python virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Optional recommended dependencies from docs/tech_stack.md.

## Claude AI News Filtering (Optional but Recommended)
For enhanced news relevance and filtering:

1. Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com)
2. Add it to the `.env` file:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```
3. Restart the dashboard. News filtering will now:
   - Use Anthropic account-available Claude models to assess article relevance to each ticker
   - Cache results for 24 hours (cheap operation)
   - Fall back to VADER sentiment-only mode if Claude unavailable
   - Toggle on/off from the dashboard UI

**Why This Feature Matters:**
- Generic yfinance news feeds often include unrelated market headlines
- Claude provides ticker-specific relevance scoring (0.0-1.0)
- Filters to top-K relevant articles before VADER sentiment analysis
- Cache layer saves ~$0.005-0.01 per ticker per day

**Dashboard Toggle:**
- Check box: "Use Claude AI for news relevance (24h cache)"
- Unchecked: Falls back to VADER-only (no LLM cost)

## Week 2 Dashboard (Dash)
Run:
python app_dash.py

## Free Hosting For iPhone Access
You do not need a separate iPhone project to use this on your phone.

Recommended path:
1. Keep this repo as the single source of truth.
2. Deploy the Dash app to a free web host such as Render.
3. Open the hosted URL in Safari on iPhone.
4. Use `Share` -> `Add to Home Screen` to install it like an app shortcut.

Minimal Render setup in this repo:
- `render.yaml` for service configuration
- `wsgi.py` as the production entrypoint
- `gunicorn` in `requirements.txt`

Typical Render configuration:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:server`
- Required environment variables: `ANTHROPIC_API_KEY` and any optional SSL flags you use locally

Important free-tier caveats:
- Free services sleep when idle, so the first load can take time.
- Local disk is ephemeral, so cache files under `data/` are not guaranteed to persist.
- Claude usage itself is not free unless your Anthropic account has free credits.

Dashboard capabilities:
- Ticker input box (comma-separated).
- Analyze action for one or many tickers.
- Scorecard view with decisions, confidence, and signal status.
- Rationale panel with reasons and context streams.
- Visual criteria breakdown cards (technical, risk, earnings, fundamentals, gating).
- Macro Meter (supportive / neutral / risk-off) with macro summary details.
- News source diversity section (Yahoo/CNBC/Reuters/MarketWatch counts).
- Floating Analysis Assistant chat bubble for questions about macro tone, RSI, risk adjustment, trend, confidence, earnings, fundamentals, and the metrics shown on the page.
- Example question chips that populate the input field; users then press Send to ask.
- Supports ticker-aware questions like "why CMCSA shows trend down" by extracting the ticker from the prompt and building on-demand context when needed.
- General concept questions are also allowed even before a stock is analyzed.
- Chat window is draggable and opens as a floating panel instead of blocking the whole page.

## Off-Hours and Provider Fallback
- The dashboard does not assume the latest calendar date always has live market data.
- If Yahoo Finance returns no daily price data for a ticker, the app now falls back to the latest cached raw snapshot available in `data/raw/` on or before the requested date.
- This helps the app stay usable during provider hiccups, off-hours, weekends, or date-range mismatches.
- When that happens, the terminal logs a warning showing that cached data was used.
- If there is no cached snapshot either, the app can optionally try Yahoo's direct chart endpoint to fetch the last available online daily history.
- In environments with SSL interception or certificate issues, enable this final fallback explicitly with:
   - `PRICE_ALLOW_INSECURE_SSL=true`
- When enabled, the dashboard also shows whether the ticker used live market data, cached data, or the direct Yahoo fallback.

## How To Interpret Confidence and RSI
- Confidence (0.00 to 1.00): composite score from technicals, NLP news sentiment, macro news, earnings, fundamentals, and risk guardrails.
- Confidence >= 0.75: strong multi-signal alignment, but still not certainty.
- Confidence 0.55-0.74: moderate signal quality, monitor for confirmation.
- Confidence < 0.55: weak/uncertain setup, prioritize caution or no action.
- RSI(14) < 30: potentially oversold (possible rebound zone, not a buy signal by itself).
- RSI(14) between 30 and 70: neutral momentum range.
- RSI(14) > 70: potentially overbought (higher pullback risk).
- RSI should always be interpreted with trend, volatility, earnings, news, and fundamentals.

## Macro News Signal
- Macro news is a market-wide backdrop signal (not company-specific).
- It ingests broad business/finance headlines from trusted external feeds.
- A lightweight keyword scorer marks macro tone as supportive, neutral, or risk-off.
- Macro tone contributes a small confidence delta and appears in the dashboard Macro Meter.

## Analysis Assistant Chat
- The floating analysis assistant is designed for page-specific explainability and stock-analysis Q&A.
- It accepts short prompts, ticker-only prompts, and general educational prompts.
- If a ticker is mentioned in the question, the app attempts to build fresh analysis context for that symbol on demand.
- The assistant now routes question intent into three modes:
   - analysis_context: explain the current dashboard decision and metrics
   - general_ticker: provide company/ticker overview even when dashboard context exists
   - general_concept: explain concepts such as RSI, ATR, confidence, macro tone
- The assistant uses the best Claude model available on the account and falls back across supported models automatically.
- The UI intentionally requires clicking Send so prompts can be reviewed before submission.

## External News Feeds
- Company news now combines:
   - yfinance company feed
   - external RSS feeds (CNBC/Reuters/MarketWatch)
- Claude relevance filtering runs after source merge and trust filtering.
- If Claude finds no relevant items, the app returns no-relevant-news (strict behavior, no raw-news fallback for that case).
- Offline behavior: when live company news fetch fails, the app reuses recent cached trusted articles from the last 15 days (when available).

## Deployment Files (Implemented)
- `render.yaml`: Render Blueprint config using `runtime: python`.
- `wsgi.py`: production WSGI entrypoint (`server = app.server`).
- `requirements.txt`: includes `gunicorn` for hosted startup command `gunicorn wsgi:server`.

## MVP Pipeline (Target)
1. Ingest market data.
2. Engineer indicators.
3. Classify trend.
4. Generate suggestion and confidence.
5. Write daily report.

## This Week Execution
Follow docs/14_day_task_board.md for day-by-day actions.

## Decision Rules and Guardrails
- Suggestion criteria and RSI thresholds: docs/decision_criteria_and_guardrails.md
- Trusted data source policy: docs/decision_criteria_and_guardrails.md
- Multi-factor final decision policy: docs/multi_factor_decision_framework.md

## Multi-Agent Upgrade Path
Start with deterministic modules, then split into:
- Coordinator Agent
- Technical Analysis Agent
- News/Sentiment Agent
- Risk Agent
- Critic Agent

Contract details are in docs/agent_prompt_contracts.md.

## Current Agent Coverage
- Technical analysis is active.
- Company news sentiment is active through a trusted news agent.
- Macro news, earnings, and fundamentals are active.
- Full-context strict gating is currently set to disabled by default to allow directional outputs during iteration.
- The in-app analysis assistant is active and can answer both general concept questions and ticker-specific questions from the dashboard.

## Motivation System
- No zero days: minimum 45 minutes.
- Ship one artifact daily.
- Friday demo cadence.
- End each day with tomorrow's first task written down.
