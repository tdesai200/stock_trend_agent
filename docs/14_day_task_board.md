# 14-Day Task Board

## Goal
Ship a reliable daily stock trend assistant MVP in 14 days, then prepare the first multi-agent upgrade.

## Product Roadmap Constraint
- Week 1 should stay command-line first.
- Week 2 should introduce a Dash dashboard.
- Week 3 should focus on interactive charts and richer visual exploration.

## ML Priority Constraint (Carry Forward)
- Feature selection is required before any final model lock.
- NLP-based news sentiment should replace keyword-only sentiment when feasible.
- Explainability must be present for model-driven recommendations.
- Time-series CV (walk-forward/expanding window) is mandatory for model evaluation.
- Ensemble modeling should be explored after baseline single-model validation.

## Rules (Motivation + Consistency)
- No zero days: minimum 45 minutes of focused work each day.
- Ship one visible artifact daily (code, test, report, or doc).
- End each day by writing tomorrow's first task.
- Friday demo even if rough.

## Week 1: MVP + Automation

### Day 1 - Scope and Definitions
- Define 5-10 target tickers.
- Define prediction horizon: next day close direction (initially).
- Define suggestion labels: Watch Buy, Hold, Reduce Risk, No Action.
- Define done criteria for MVP report.
- Output: project scope document and symbol list.

### Day 2 - Data Ingestion
- Pull OHLCV daily data for each ticker.
- Add basic retry and missing-data checks.
- Save raw snapshots in data/raw/YYYY-MM-DD/.
- Output: ingestion script + first raw snapshot.

### Day 3 - Feature Engineering
- Build indicators: SMA(20/50), EMA(12/26), RSI(14), ATR(14), momentum(5).
- Save engineered table in data/processed/YYYY-MM-DD/.
- Output: features pipeline.

### Day 4 - Trend Classification
- Implement baseline trend rules:
  - Uptrend: price > SMA20 > SMA50 and RSI > 50.
  - Downtrend: price < SMA20 < SMA50 and RSI < 50.
  - Else Neutral.
- Output: trend labels for all symbols.

### Day 5 - Suggestion Engine
- Map trend + volatility + volume into suggestions.
- Add confidence score (0-1) with clear rationale components.
- Output: suggestion JSON for all symbols.

### Day 6 - Report Generator
- Generate daily markdown report in reports/daily/YYYY-MM-DD.md.
- Sections: summary table, per-symbol rationale, risk notes.
- Output: first readable daily report.

### Day 7 - Daily Scheduler
- Add single command run_all to execute full pipeline.
- Add Task Scheduler or cron equivalent for market days.
- Output: one-click pipeline and schedule doc.

## Week 2: Quality + First Agent Split

### Day 8 - Logging and Observability
- Add structured logs and run metadata.
- Track run duration, failed symbols, missing fields.
- Output: run log file and metrics summary.

### Day 9 - Backfill and Evaluation
- Backfill 6-12 months for selected symbols.
- Evaluate trend hit rate for baseline strategy.
- Output: evaluation script + baseline metrics.

### Day 10 - Risk Controls
- Add simple risk guardrails (high volatility downgrade, stop-risk flag).
- Output: risk-adjusted suggestion logic.

### Day 11 - News/Sentiment Agent (First Specialist)
- Add a lightweight news summary component.
- Score sentiment (positive/neutral/negative) and include in rationale.
- Output: sentiment-enriched daily report.

Status:
- Completed and expanded beyond original scope.
- Includes multi-source ingestion (yfinance + external RSS), Claude relevance filtering, strict no-relevant-news behavior, and source diversity reporting in dashboard rationale.

### Day 12 - Agent Refactor (Coordinator + Specialists)
- Split into Coordinator Agent + Technical Agent + Risk Agent.
- Keep same output schema.
- Output: multi-agent orchestration skeleton.

### Day 13 - Critic Agent
- Add a critic pass that can challenge low-evidence suggestions.
- Require final report to include critic comments when confidence < threshold.
- Output: critic review section.

### Day 14 - Demo + Next Sprint Plan
- Run full system for all symbols.
- Record wins, gaps, and next sprint backlog.
- Output: Sprint 2 plan and prioritized tasks.

## Week 3 Preview: Dash Dashboard
- Add a Dash app for single-ticker and multi-ticker analysis.
- Show final decision, technical signal, news sentiment, and missing domains.
- Add a ticker input box and an Analyze action.
- Add a compact scorecard view for trend, RSI, confidence, and recommendation.

Status:
- Implemented and extended.
- Dashboard now includes criteria breakdown cards, macro meter, trend badges, source attribution, explicit startup/session guardrails, and a floating Analysis Assistant.
- The assistant supports general concept questions, ticker-aware prompts, example suggestions, Send-based submission, and on-demand context resolution when a ticker is named in the prompt.
- The assistant now differentiates between current-analysis questions and general company-overview questions for the same ticker.
- The assistant window is draggable and opens as a floating panel so it does not block the main analysis flow.
- Market-data resilience now includes live yfinance, cached raw snapshot fallback, and an optional last-available-online Yahoo chart fallback with status shown in the dashboard.
- Company-news resilience includes a recent-cache fallback window (15 days) when live news fetch is unavailable.
- Deployment preparation is in place for hosted/mobile use (`wsgi.py`, `render.yaml`, `gunicorn`).

## Week 4 Preview: Interactive Charts
- Add interactive candlestick and volume charts.
- Overlay SMA/EMA lines and RSI panel.
- Add hover details, range selectors, and side-by-side ticker comparison.
- Support drilling from portfolio view into single-ticker detail.

## Daily Standup Template (2 minutes)
- Yesterday I shipped:
- Today I will ship:
- Current blocker:
- First task tomorrow:
