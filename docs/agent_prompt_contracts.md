# Multi-Agent Prompt Contracts

## Shared Output Schema
All agents return JSON with:
- symbol: string
- as_of_date: string (YYYY-MM-DD)
- evidence: array of strings
- confidence: float (0-1)
- warnings: array of strings
- status: success | partial | failed

## 1) Coordinator Agent

### Mission
Orchestrate specialist agents and produce final daily suggestion package.

### Inputs
- list of symbols
- as_of_date
- market context

### Responsibilities
- Request outputs from specialist agents.
- Resolve conflicts using confidence and evidence quality.
- Produce final suggestion per symbol with rationale.

### Output Additions
- suggestion: Watch Buy | Hold | Reduce Risk | No Action
- rationale_top3: array of 3 concise reasons
- contributing_agents: array of agent names

### Current UI Note
- The dashboard ships with an in-app Analysis Assistant that explains the coordinator output, current metrics, and page-level analysis terms in plain language.
- The assistant accepts both general stock-analysis questions and ticker-specific prompts that mention a symbol directly.

## 2) Technical Analysis Agent

### Mission
Compute trend signals from OHLCV and technical indicators.

### Inputs
- feature table per symbol

### Responsibilities
- Determine trend state: Uptrend | Neutral | Downtrend.
- Report key indicator evidence and directional agreement.

### Output Additions
- trend_state
- indicator_snapshot: object

### Current UI Note
- The dashboard can surface technical-analysis explanations through the assistant, including trend state, RSI, momentum, and volatility guardrails.

## 3) News and Sentiment Agent

### Mission
Summarize recent material news and infer sentiment impact.

### Inputs
- recent headlines/news snippets

### Responsibilities
- Identify 1-3 material events.
- Classify sentiment: positive | neutral | negative.
- Explain likely short-term impact.

### Output Additions
- sentiment
- material_events

### Current Implementation Note
- The current implementation includes trusted company news scoring (yfinance + trusted external RSS), plus active macro, earnings, and fundamentals streams in the final decision pipeline.
- Company-news logic can reuse trusted cached items (15-day window) if live retrieval is temporarily unavailable.
- Company-news output can adjust confidence and downgrade bullish technical setups when trusted company news is negative.

### Current UI Note
- The assistant can explain how company news, macro tone, and source filtering affect the current recommendation.
- The assistant can distinguish current-analysis questions from general ticker/company overview questions.

## Deployment and Channel Note
- Local run mode remains `python app_dash.py`.
- Hosted run mode uses `gunicorn wsgi:server`.
- Render blueprint config is provided in `render.yaml` for web deployment and mobile browser access.

## 4) Risk Agent

### Mission
Detect elevated risk conditions and enforce caution.

### Inputs
- volatility metrics
- concentration/exposure context
- recent drawdown data

### Responsibilities
- Flag high-risk setups.
- Suggest confidence penalty when uncertainty is high.

### Output Additions
- risk_level: low | medium | high
- risk_flags: array
- confidence_penalty: float (0-0.5)

### Current UI Note
- The assistant can explain ATR, risk adjustment, and why a setup was downgraded or capped.

## 5) Critic Agent

### Mission
Challenge weak recommendations before release.

### Inputs
- coordinator draft suggestion
- all specialist outputs

### Responsibilities
- Find missing evidence, contradictions, and overconfidence.
- Request downgrade or No Action when support is weak.

### Output Additions
- critic_verdict: approve | caution | reject
- critic_notes

### Current UI Note
- Future assistant expansion should be able to summarize critic reasoning and missing evidence in short, user-facing language.

## Merge Policy
- If Risk Agent risk_level = high and confidence < 0.65, cap suggestion to Hold or No Action.
- If Critic Agent verdict = reject, final suggestion cannot be Watch Buy.
- If Technical and Sentiment strongly disagree, reduce confidence by at least 0.1.

## Guardrails
- Do not claim certainty.
- Always include uncertainty factors.
- Use language consistent with decision support, not financial advice.
