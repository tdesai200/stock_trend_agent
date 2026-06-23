# Product Features (v1.0)

Last Updated: June 23, 2026

## Landing & Onboarding
- ✅ Hero section with product value proposition
- ✅ "Why This Product Is Useful" section (pain point framing)
- ✅ "What Value You Get" benefits panel
- ✅ "How It Works" 3-step pipeline
- ✅ Smooth CTA buttons with anchor navigation
- ✅ Dynamic scorecard jump CTA (enabled only after analysis)
- ✅ Custom tooltip on disabled CTAs for user guidance

## Watchlist Management
- ✅ Save up to 20 tickers as persistent watchlist
- ✅ Watchlist stored in `data/watchlist.json` (survives page reload)
- ✅ Visual watchlist chips for quick reference
- ✅ Watchlist validation (ticker format, duplicate removal)
- ✅ Reuse watchlist in both manual analyzer and daily signals
- ✅ Status indicator on save (success + symbol count)

## Daily Watchlist Signals
- ✅ One-click "Run Daily Signals" button
- ✅ Daily Watchlist Signals table with explainable data:
  - Symbol, Trend (UP/DOWN/NEUTRAL), Decision, Confidence
  - **Explainable Reason**: Top reason for current decision
  - **Trusted Headlines**: 1-2 most relevant news items filtered by source
- ✅ Trend reversal notifications (uptrend ↔ downtrend detection)
- ✅ Signal history saved in `data/watchlist_daily_signals.json` (30-day retention)
- ✅ Prior trend lookup for reversal alert generation

## Core Analysis Engine
- ✅ Multi-tick analysis in single run
- ✅ Confidence scoring (0.0-1.0) from:
  - Technical indicators (RSI, ATR, momentum, trend)
  - News sentiment (NLP + Claude relevance filtering)
  - Macro tone (supportive/neutral/risk-off)
  - Earnings context (available / not available)
  - Fundamentals context (available / not available)
  - Full-context guardrails (gating)

## Decision Transparency
- ✅ Scorecard table with symbol, trend, decision, confidence, RSI, status
- ✅ Rationale panel with:
  - Expandable summary per ticker
  - Criteria breakdown cards (technical, risk, news, earnings, fundamentals, gating)
  - Macro meter (visual gradient + commentary)
  - News sources used (count by domain)
  - Earnings and fundamentals context
- ✅ Any reason is a user-facing explainable string
- ✅ No jargon without explanation

## News & Information
- ✅ Trusted-source filtering (Reuters, CNBC, MarketWatch, Yahoo Finance)
- ✅ Claude AI relevance scoring (configurable via UI toggle):
  - ON: Uses Claude to score ticker relevance per article
  - OFF: Falls back to VADER sentiment only (no Claude cost)
- ✅ 24-hour cache for Claude relevance results
- ✅ Graceful degradation if Claude unavailable (VADER fallback)
- ✅ Up to 3 headlines displayed per ticker in daily signals

## Market Data Reliability
- ✅ Live data priority: yfinance → Yahoo chart fallback → cached snapshot
- ✅ Data freshness badges:
  - **LIVE Yahoo**: In-market yfinance data
  - **FALLBACK Yahoo Direct**: Yahoo chart endpoint (slightly delayed)
  - **CACHED Snapshot**: Historical disk data (clearly marked)
  - **UNKNOWN**: Source not detected
- ✅ Off-hours behavior: No crash, clear fallback label
- ✅ Fallback retry logic with 3-second backoff
- ✅ Raw snapshot cache in `data/raw/{date}/` auto-populated

## In-App Analysis Assistant
- ✅ Floating chat bubble (bottom-right, draggable)
- ✅ Question routing to 3 modes:
  - analysis_context: Explain current dashboard decision
  - general_ticker: Company overview even without current analysis
  - general_concept: Explain RSI, confidence, macro tone, etc.
- ✅ Ticker extraction from free-text prompts
- ✅ Example question chips (pre-populated suggestions)
- ✅ Per-session question limit (configurable, default 20)
- ✅ Model fallback: Try best available Claude 3.5 → Opus → Haiku
- ✅ Graceful degradation if Claude unavailable

## Session & Settings
- ✅ Session ID + startup timestamp in info card
- ✅ Claude news filter status indicator (working/unavailable/fallback)
- ✅ As-of date picker for historical signal runs
- ✅ News filtering mode toggle (Claude on/off)
- ✅ Interpretation guide (Confidence, RSI, Macro tone explained)

## Error Handling
- ✅ Guardrail-driven validation:
  - Ticker format checking
  - Insufficient market history protection (min 50 days)
  - Too many tickers in one request protection
  - Future date rejection
- ✅ User-friendly error panels with specific error codes
- ✅ Graceful handling of missing data:
  - No technicals available → marked in criteria
  - No news available → "No trusted headlines"
  - No earnings → marked as not available
  - No fundamentals → marked as not available

## UI/UX Polish
- ✅ Hero fade animation on page load
- ✅ Smooth anchor-link navigation (landing to analyzer, landing to scorecard)
- ✅ Responsive grid layout (mobile-friendly)
- ✅ Readable typography (14px base, proper contrast)
- ✅ Color scheme:
  - Deep blue hero with gradient overlay
  - Light backgrounds for card content
  - Green for positive (UP, bullish signals)
  - Red for negative (DOWN, risk alerts)
  - Neutral gray for indifferent signals
- ✅ Custom styled tooltip on disabled CTA (instead of browser native title)

## Deployment Ready
- ✅ Render.yaml for free hosting
- ✅ WSGI entrypoint (wsgi.py) for gunicorn
- ✅ Requirements.txt with all dependencies
- ✅ Graceful handling of environment variables:
  - ANTHROPIC_API_KEY (optional, for Claude news filtering)
  - PRICE_ALLOW_INSECURE_SSL (optional, for SSL interception)
  - PORT (optional, default 8051)
  - HOST (optional, default 127.0.0.1)

## Roadmap (Not Yet Implemented)

### v1.1 - App Store Submission
- [ ] Disclaimer modal on first app load
- [ ] Settings screen with Privacy Policy, Terms, Support contact
- [ ] Loading spinners on all async operations
- [ ] Empty state messaging
- [ ] Mobile responsiveness fixes
- [ ] App icon + 5 screenshots for App Store
- [ ] User account system (optional cloud sync)
- [ ] Push notifications (trend reversals, daily digest)

### v2.0 - Mobile Expansion
- [ ] React Native or Flutter app
- [ ] Cloud-backed user accounts with watchlist sync
- [ ] Biometric auth
- [ ] App widget (iOS) or glance (visionOS)
- [ ] Siri shortcut integration
- [ ] Focus modes (Do Not Disturb integration)

### v3.0 - Personalization
- [ ] Risk appetite profile (conservative/moderate/aggressive)
- [ ] Custom scoring weights (user can tune technical vs news vs macro)
- [ ] Backtesting engine (\"what if\" historical analysis)
- [ ] Saved analysis snapshots (compare day-over-day)
- [ ] Export reports as PDF

### Later - Community & Monetization
- [ ] Leaderboard (public watchlist performance tracking)
- [ ] Community ideas/discussion (Reddit-like)
- [ ] Affiliate links to brokers (disclosure compliant)
- [ ] Pro tier (advanced analytics, API access, CSV exports)
- [ ] Team collaboration (shared watchlists, alerts)

---

## Technical Stack
See `docs/tech_stack.md` for full details.

**Frontend**: Dash (Python + React under hood)
**Backend**: Python (src/ analysis modules)
**Market Data**: yfinance + Yahoo Finance direct endpoint
**News**: yfinance RSS + external feeds (Reuters, CNBC, MarketWatch)
**NLP Sentiment**: VADER + Claude 3.5 Sonnet (if available)
**Storage**: Local JSON files (watchlist, signals, cache)
**Deployment**: Render (free tier), Gunicorn
**Auth**: None yet (planned for v1.1+ mobile)

---

## Known Limitations (v1.0)

1. **No user accounts**: Watchlist is app-wide, not per-user
2. **No mobile app**: Web only (mobile browser works, responsive needs polish)
3. **No scheduled jobs**: Signals must be manually triggered
4. **No data export**: Can't download reports yet
5. **No historical comparison**: Can't see \"how did this signal perform yesterday?\"
6. **No portfolio tracking**: Can't upload holdings for personalized alerts
7. **No backtesting**: Can't run historical simulations
8. **Limited to 20 symbols**: Watchlist size capped for reliability
9. **No price alerts**: Only trend reversal notifications
10. **No advanced charting**: Dash table only, no TradingView-style charts

---

## Tested Scenarios

✅ Add watchlist with 10 tickers  
✅ Run daily signals and see trend reversals  
✅ View explainable reasons for each ticker  
✅ Read trusted headlines without irrelevant news  
✅ Ask chat assistant about RSI and confidence  
✅ Navigate landing page to analyzer and scorecard  
✅ Save watchlist and reload page (persistence)  
✅ Fall back to cached data when yfinance unavailable  
✅ Use Claude news filtering and toggle off  
✅ Analyze 5+ tickers in single run  
✅ See confidence bands and criteria breakdown  
✅ Encounter and handle error gracefully (insufficient history, invalid ticker)  

---

## Metrics to Track for App Store

### User Acquisition
- Downloads
- Install-to-first-analysis conversion rate
- Watchlist creation rate

### Engagement
- Daily active users (DAU)
- Session length (avg)
- Analyses per user per day
- Daily signals runs per user
- Chat questions asked per user

### Retention
- Day 1, Day 7, Day 30 retention rates
- Churn (users who used app once and never returned)

### Quality
- Crash rate (target: <1%)
- App Store rating (target: 4.0+)
- User review sentiment

---

## Bug Reports & Feedback

Report issues: GitHub Issues on this repo  
Feature requests: GitHub Discussions  
Security vulnerability: report privately to maintainers
