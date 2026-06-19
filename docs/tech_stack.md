# Recommended Tech Stack

## Core Language
- Python 3.11+

## Data and Indicators
- pandas: tabular transformation and joins.
- numpy: numeric operations.
- ta: technical indicators (already in requirements).
- yfinance: initial data source for MVP.
- requests: external RSS ingestion (CNBC/Reuters/MarketWatch feeds).
- xml.etree.ElementTree: RSS parsing.

## Agent and Orchestration Layer
- Start simple: deterministic Python modules + coordinator function.
- Upgrade path:
  - Option A: lightweight function-calling with your preferred LLM SDK.
  - Option B: dedicated agent framework once interfaces stabilize.

## Storage
- Local files for MVP:
  - data/raw/YYYY-MM-DD/
  - data/processed/YYYY-MM-DD/
  - reports/daily/YYYY-MM-DD.md
  - reports/history/suggestions.parquet
- Future: SQLite or Postgres for versioned signal history.

## Automation
- Windows Task Scheduler to run daily after market close.
- Single entrypoint command: python -m src.main run-all --date YYYY-MM-DD

## Quality and Reliability
- pytest for unit tests.
- ruff for linting.
- black for formatting.
- pydantic for validated config and outputs.
- tenacity for retry logic on external data calls.

## Visualization (Optional in Sprint 2)
- matplotlib or plotly for trend charts in reports.

## UI Roadmap
- Week 1: CLI output using the current Python entrypoint.
- Week 2: Dash for the first dashboard experience.
- Week 3: Plotly charts inside Dash for interactive exploration.

## Current Dashboard State (Implemented)
- Stock-themed Dash UI with hero visual and responsive card layout.
- Scorecard with trend indicator badges.
- Rationale panel with criteria breakdown cards.
- Macro Meter visualization (supportive / neutral / risk-off).
- News source diversity section per ticker.
- Floating Analysis Assistant chat bubble with draggable panel behavior.
- Example question shortcuts, Send-based submission, and ticker-aware question handling.
- Dynamic Claude model selection so the assistant uses an available model from the account instead of a hardcoded model id.

## ML Technique Commitments
- Feature selection: use filter and model-based importance methods to keep only signal-bearing features.
- NLP news sentiment: move from keyword sentiment to NLP-based sentiment scoring for company news.
- Explainability: provide per-ticker feature attribution for every model-driven recommendation.
- Time-series cross-validation: use walk-forward or expanding-window splits only.
- Ensemble models: combine at least two complementary learners for robust directional classification.

## Recommended ML Toolkit For Next Phases
- scikit-learn: feature selection, metrics, pipelines, and time-series CV utilities.
- xgboost and/or lightgbm: tree-based boosted models for tabular market features.
- shap: local and global explainability for model outputs.
- nltk, vaderSentiment, or transformers: NLP sentiment modeling for news text.

## Suggested Requirements Additions
- pydantic
- tenacity
- pytest
- ruff
- black
- pyarrow

## Current Runtime Requirements (Implemented)
- yfinance
- pandas
- numpy
- ta
- lxml
- vaderSentiment
- dash
- anthropic
- python-dotenv
- requests
- gunicorn

## Current Chat Runtime Notes
- The chat assistant accepts short prompts and general conceptual questions.
- If a ticker appears in the prompt, the app attempts to resolve it and build current analysis context for that symbol.
- The assistant uses a model fallback chain and caches the first available Claude model discovered during the session.
- The assistant now applies question-intent routing:
  - analysis_context (current dashboard metrics and decision)
  - general_ticker (company overview requests)
  - general_concept (educational definitions)

## Current Market Data Resilience Notes
- Primary daily OHLCV source is yfinance.
- If live daily data is unavailable, the app falls back to the latest cached raw snapshot in `data/raw/`.
- If no cached snapshot exists, the app can optionally use Yahoo's direct chart endpoint to fetch the last available online data.
- The direct chart fallback may require `PRICE_ALLOW_INSECURE_SSL=true` in environments with SSL certificate interception.

## Current Company News Resilience Notes
- Primary company-news source remains yfinance plus trusted external RSS feeds.
- If live company-news retrieval fails, the app can reuse trusted cached articles published within the last 15 days.
- This allows sentiment/reasoning continuity during temporary provider/network outages.

## Deployment Runtime Notes
- Local development entrypoint: `python app_dash.py`
- Hosted entrypoint: `gunicorn wsgi:server`
- Render Blueprint file: `render.yaml` with `runtime: python` (not `env: python`)

## Planned UI Dependencies
- dash
- plotly

Add these when the Dash and chart work starts, not before.

## Planned ML Dependencies
- scikit-learn
- shap
- xgboost or lightgbm
- nltk or vaderSentiment (or transformers if needed)

Add these when model training and NLP sentiment implementation starts.

## Why this stack
- Fastest path to a working MVP this week.
- Easy to keep deterministic and testable.
- Natural upgrade path from single-agent to multi-agent without rewriting data pipelines.
