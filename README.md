# Stock Trend Agent

AI-assisted market insights platform that transforms fragmented stock analysis workflows into one explainable decision surface with confidence scoring, multi-source news, and watchlist-driven daily signals.

Designed for both web dashboards and eventual mobile app (planned v1.1+ for iOS/Android via App Store).

## Current Status: V1 Web MVP
- ✅ Landing page with product value proposition
- ✅ Multi-ticker analyzer with confidence-driven decisions
- ✅ Explainable rationale with criteria breakdown
- ✅ Persistent watchlist management
- ✅ Daily watchlist signals with trend reversal alerts
- ✅ In-app analysis assistant (ticker and concept Q&A)
- ✅ Trusted-source news filtering (with Claude relevance scoring)
- ✅ Macro meter and multi-factor signal fusion

## Roadmap: App Store Submission (Target Q4 2026)
See `docs/app_store_roadmap.md` for compliance, architecture, and launch checklist.

## Project Structure
- **app_dash.py**: Main Dash web application (UI, callbacks, watchlist, signals)
- **src/**: Analysis pipeline (technical, news, earnings, fundamentals, macro)
- **data/**: Market data snapshots, watchlist, and daily signal runs
  - `watchlist.json`: Saved ticker watchlist
  - `watchlist_daily_signals.json`: Historical daily signal runs
- **docs/**: Product planning, decision criteria, app store roadmap
- **assets/**: CSS styling, market hero SVG, chat interface styles
- **reports/**: Generated daily reports (markdown format)
- **wsgi.py**: Production WSGI entrypoint for Render deployment

## Setup
1. Create and activate a Python virtual environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Optional recommended dependencies from docs/tech_stack.md.

## Claude AI News Filtering (Optional but Recommended)
For enhanced news relevance and filtering:

1. Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com)
2. For local development, add it to the `.env` file:
   ```
   ANTHROPIC_API_KEY=your_key_here
   ```
3. For Render, add the same key in `Render Dashboard > Your Service > Environment` as `ANTHROPIC_API_KEY`. Do not include quotes around the value.
4. Restart the dashboard locally, or redeploy/restart the Render service. News filtering will now:
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

## Quick Start

### Local Development
```bash
python app_dash.py
```
Opens browser at `http://127.0.0.1:8051`

### First-Time User Flow
1. View landing page with product value proposition
2. Accept disclaimer (compliance requirement)
3. Create or import watchlist (up to 20 tickers)
4. Click "Run Daily Signals" to populate today's signals
5. Review daily scorecard with explainable reasons and trusted headlines
6. Check trend reversal alerts to act on reversals early
7. Use analysis assistant for explanations

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
- `render.yaml` marks `ANTHROPIC_API_KEY` as `sync: false`, so Render will not copy your laptop `.env`; set the secret manually in the Render dashboard.

Important free-tier caveats:
- Free services sleep when idle, so the first load can take time.
- Local disk is ephemeral, so cache files under `data/` are not guaranteed to persist.
- Claude usage itself is not free unless your Anthropic account has free credits.

## Dashboard Features

### Landing Page
- Product value proposition with pain-point framing
- "Why This Product Is Useful" section explaining workflow consolidation
- "What Value You Get" highlighting key benefits
- "How It Works" 3-step pipeline explanation
- CTA buttons with smooth anchor linking

### Watchlist Management
- Save up to 20 tickers as persistent watchlist
- Watchlist displays as visual chips for quick reference
- Shared watchlist in both analyzer and daily signals sections
- Watchlist stored in `data/watchlist.json` (persistent across sessions)

### Daily Signals
- One-click "Run Daily Signals" button
- Daily Watchlist Signals table with:
  - Symbol, Trend, Decision, Confidence
  - **Explainable Reason**: Top reason for current decision
  - **Trusted Headlines**: 1-2 most relevant news items
- **Trend Reversal Alerts**: Notification panel showing uptrend→downtrend or vice versa
- Signal history saved in `data/watchlist_daily_signals.json` (30-day retention)

### Analyzer & Scorecard
- Manual ticker input (comma-separated) or load from watchlist
- Analyze action for one or many tickers
- Scorecard view with decisions, confidence, and signal status
- Detailed rationale panel with reasons and context streams
- Visual criteria breakdown cards (technical, risk, earnings, fundamentals, gating)
- Macro Meter (supportive / neutral / risk-off) with macro summary
- News source diversity section (Yahoo/CNBC/Reuters/MarketWatch counts)

### Analysis Assistant (Chat Bubble)
- Floating chat interface for ticker and concept Q&A
- Questions routing:
  - **analysis_context**: Explain current dashboard decision
  - **general_ticker**: Company/ticker overview
  - **general_concept**: Explain RSI, trend, confidence, macro tone
- Supports ticker extraction (e.g., "why CMCSA shows trend down")
- Example question chips for quick prompts
- Draggable modal window

## Data Quality & Fallback Strategy
The dashboard prioritizes live online data with intelligent fallback to maintain reliability:

1. **Live Data (Preferred)**: yfinance daily OHLCV
2. **Online Fallback**: Yahoo chart endpoint (if yfinance fails)
3. **Cache Fallback**: Latest snapshot from `data/raw/` (only if online unavailable)

Each analysis shows a data freshness badge:
- **LIVE Yahoo**: In-market data from yfinance
- **FALLBACK Yahoo Direct**: Yahoo chart endpoint (slightly delayed)
- **CACHED Snapshot**: Historical data from disk (clearly marked)
- **UNKNOWN**: Data source not detected

For SSL interception environments, enable:
```bash
export PRICE_ALLOW_INSECURE_SSL=true
```

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

## Product Compliance & Trust
- All UI text uses education-first, non-advisory language
- Clear "This is not financial advice" messaging throughout
- Future versions will add:
  - Mandatory disclaimer modal on first app load
  - User account system with privacy controls
  - Data deletion endpoint
  - Support contact form in settings

See `docs/app_store_roadmap.md` for full compliance checklist.

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

## Next Steps (Toward App Store v1)
Prioritized roadmap:
1. **Week 1**: Add disclaimer modal, Settings page, Privacy/Terms links
2. **Week 2**: Loading states, empty state messaging, error retry logic
3. **Week 3**: Mobile responsiveness audit, app icon creation, screenshots
4. **Week 4**: Privacy policy, TestFlight submission, review cycle

See `docs/app_store_roadmap.md` for detailed sprint plan and success criteria.
