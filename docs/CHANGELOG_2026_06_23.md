# Changelog: June 23, 2026 - Landing Page & Watchlist MVP

## Overview
Transformed Stock Trend Agent from pure analyzer tool into a consumer-ready product with landing-page positioning, persistent watchlist management, daily signals, and trend-reversal notifications.

## Major Feature Additions

### 1. Landing Page & Value Proposition
- **New**: Hero-to-analyzer flow with landing sections above analyzer
- **Sections**: "Why Useful", "What You Get", "How It Works"
- **Navigation**: Smooth anchor linking (Start Analyzing → Jump to Scorecard)
- **UX**: Dynamic scorecard CTA (gated until analysis exists, custom tooltip)
- **Files Changed**: `app_dash.py`, `assets/dashboard.css`

### 2. Persistent Watchlist Management
- **New**: Save up to 20 tickers in `data/watchlist.json`
- **Features**:
  - Watchlist UI section with input + Save button
  - Visual watchlist chips for quick reference
  - Reuse watchlist in both analyzer and daily signals
  - Validation (format, duplicates, limits)
- **Files Changed**: `app_dash.py`, `assets/dashboard.css`
- **New Functions**: `_load_watchlist()`, `_save_watchlist()`, `_parse_watchlist()`

### 3. Daily Watchlist Signals
- **New**: One-click signal run for entire watchlist
- **Table Columns**:
  - Symbol, Trend, Decision, Confidence
  - Explainable Reason (top reason for decision)
  - Trusted Headlines (1-2 most relevant news items)
- **Notifications**: Trend reversal alerts (uptrend ↔ downtrend)
- **History**: Signal runs saved in `data/watchlist_daily_signals.json` (30-day retention)
- **Files Changed**: `app_dash.py`, `assets/dashboard.css`
- **New Functions**: `_upsert_daily_signal_run()`, `_get_previous_trends()`

### 4. Market Data Priority (Online First)
- **Changed**: Updated fallback order in `src/data_ingestion.py`
  - Priority 1: yfinance live data (preferred)
  - Priority 2: Yahoo chart endpoint (online fallback)
  - Priority 3: Cached snapshots (only if online unavailable)
- **Rationale**: Ensures cache is used only when live data truly unavailable
- **Files Changed**: `src/data_ingestion.py`

### 5. Compliance & UX Foundation
- **New Styling**: Custom tooltip for disabled scorecard CTA
- **Foundation**: Code structure ready for v1.1 disclaimer modal, settings page
- **Documentation**: Added `docs/app_store_roadmap.md` with 5-week plan

## Documentation Updates

### Files Updated
- ✅ `README.md`: Full refresh with landing page, watchlist, daily signals features
- ✅ `requirements.txt`: Verified all dependencies (no new ones needed)
- ✅ `docs/app_store_roadmap.md`: **NEW** - Complete v1 submission plan
- ✅ `docs/product_features_v1.md`: **NEW** - Full feature inventory with roadmap

### Key Sections
1. **README.md**: Restructured to highlight product vision, features, and App Store path
2. **app_store_roadmap.md**: 6 phases covering compliance, reliability, architecture, assets, TestFlight, launch
3. **product_features_v1.md**: Complete feature list, tested scenarios, known limitations, metrics

## Validation

### Syntax & Errors
- ✅ No Python errors in `app_dash.py` (compile check passed)
- ✅ No CSS errors in `assets/dashboard.css`
- ✅ No errors in `src/data_ingestion.py`

### Callbacks Tested
- ✅ Watchlist save → persistence + UI update
- ✅ Daily signals run → table population + trend reversal detection
- ✅ Scorecard CTA gating → disabled until analysis exists
- ✅ Tooltip display → custom styled tooltip on hover

### Backward Compatibility
- ✅ All existing analyzer callbacks unchanged
- ✅ All existing chat assistant callbacks unchanged
- ✅ All existing data analysis pipeline unchanged
- ✅ Only new UI sections added (no breaking changes)

## Breaking Changes
**None.** All changes are additive. Existing users will see new sections but all current workflows remain intact.

## Migration Path for Users
1. No action needed. Existing ticker input flow unchanged.
2. Optional: Save tickers to persistent watchlist via new UI.
3. Optional: Use daily signals run for faster multi-ticker analysis.

## Performance Impact
- **JSON I/O**: Minimal (watchlist ~1KB, signals ~10KB per 30 days)
- **UI Rendering**: New sections lazy-loaded, no impact on analyzer performance
- **API Calls**: No new external dependencies, same data sources

## Next Steps (Toward v1.0 App Store)

**Week 1 (Priority 1 - Compliance)**
- [ ] Add disclaimer modal on first app load
- [ ] Add Settings page with Privacy/Terms/Support links
- [ ] Write Privacy Policy + Terms of Use docs

**Week 2 (Priority 2 - Reliability)**
- [ ] Add loading spinners on async buttons
- [ ] Add empty state messaging
- [ ] Add error retry logic with backoff

**Week 3 (Priority 3 - Assets)**
- [ ] Mobile responsiveness audit
- [ ] Create app icon (1024x1024)
- [ ] Capture 5+ screenshots for App Store

**Week 4 (Priority 4 - TestFlight)**
- [ ] Build for iOS
- [ ] Submit to TestFlight (internal beta)
- [ ] Iterate based on feedback

**Week 5 (Priority 5 - Launch)**
- [ ] App Store submission
- [ ] Monitor review cycle
- [ ] Prepare day-1 launch announcement

## Code Quality
- **Comments**: Clear inline comments for new helpers
- **Function names**: Descriptive (`_load_watchlist`, `_upsert_daily_signal_run`, etc.)
- **Error handling**: Graceful with user-facing messages
- **Testing**: Manual walkthrough of new features completed

## Known Issues / Technical Debt
1. Watchlist is app-wide (not per-user) - planned for v1.1 with accounts
2. Daily signals must be manually triggered - planned scheduled job in v1.1
3. No data export - planned for v2.0
4. Mobile responsive CSS needs audit - planned for v1.1 TestFlight

## Questions for Next Sprint Planning
1. When to implement user accounts (v1.0 or v1.1)?
2. Should watchlist auto-run daily at market open (requires background job)?
3. Priority: iOS first, or also target Android (TestFlight vs Google Play)?
4. Should we do legal review before App Store submission?

---

**Deployed to**: Local development (`python app_dash.py`)  
**Render deployment**: Next step (ensure env variables set in Render dashboard)  
**Testing**: Manual browser testing on Chrome/Safari  
**Branch**: main (ready for deployment)
