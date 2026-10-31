# GLOBAL MARKET INTELLIGENCE
## Software Requirements Specification (SRS) & Technical Implementation Blueprint

**Project:** Global Market Intelligence (GMI)  
**Version:** 1.0  
**Project Type:** Multi-Asset AI Financial Intelligence, Forecasting & Paper Trading Platform  
**Primary Language:** Arabic / English  
**Implementation:** Next.js + Python FastAPI + PostgreSQL + Machine Learning  
**AI Development Assistant:** Claude Code  
**Trading Mode:** Paper Trading Only – No Real-Money Execution

> This document is the source of truth for requirements. Approved deviations and decisions
> taken after review are recorded in `docs/architecture/IMPLEMENTATION_PLAN.md` §0
> ("Approved decisions") and take precedence where they explicitly amend this text.

---

# 1. PROJECT VISION

Build an institutional-style financial intelligence platform that analyzes, monitors, forecasts, and simulates trading across three financial instruments:

1. USD/ILS – US Dollar versus Israeli Shekel.
2. XAU/USD – Gold versus US Dollar.
3. BTC/USD – Bitcoin versus US Dollar.

All three instruments must receive equal product-level priority.

The system must operate as a collection of independent analytical engines coordinated by a central AI intelligence layer.

The platform must not behave like a simple chatbot. It must retrieve real market data, calculate technical indicators, analyze macroeconomic events, evaluate financial news, execute quantitative forecasting models, generate probability-based scenarios, simulate trades, and continuously evaluate its own historical performance.

## 1.1 Primary objectives

- Monitor all three markets.
- Collect and preserve historical market data.
- Analyze technical, fundamental, macroeconomic, and geopolitical factors.
- Generate forecasts across multiple time horizons.
- Produce explainable bullish, bearish, and neutral scenarios.
- Generate trading signals.
- Execute simulated trades through an internal paper trading engine.
- Measure model performance objectively.
- Provide importer-oriented currency purchasing analysis.
- Deliver automated alerts and reports.

## 1.2 Non-negotiable principles

1. Never fabricate prices, indicators, news, or market statistics.
2. Every market observation must have a source and timestamp.
3. Every forecast must be stored before its outcome is known.
4. Never use future data in historical model training or backtesting.
5. Never present an AI-generated opinion as a verified market fact.
6. Never execute real-money trades in version 1.
7. Never produce a high-confidence signal when data quality is insufficient.
8. Every model must be evaluated against a simple baseline.
9. All forecasts must have an expiry time and an invalidation condition.
10. Market data licensing and provider usage restrictions must be respected.

---

# 2. SUPPORTED MARKETS

## 2.1 Market configuration

| Instrument | Market | Priority | Trading hours |
|---|---|---|---|
| USD/ILS | Forex | Equal | Market-dependent, generally 24/5 |
| XAU/USD | Precious metals | Equal | Provider-defined, generally 24/5 |
| BTC/USD | Cryptocurrency | Equal | 24/7 |

The three instruments must use independent market configurations, data sources, model parameters, risk settings, and performance records.

Equal priority means equal product importance, not identical data availability or identical forecasting methods.

## 2.2 Asset-specific analytical requirements

### USD/ILS Engine

Monitor:

- Bank of Israel exchange-rate publications.
- Live USD/ILS market quotes.
- US Federal Reserve policy.
- Bank of Israel interest-rate decisions.
- US and Israeli inflation.
- Employment data.
- US Treasury yields.
- Dollar Index (DXY).
- Geopolitical and security developments.
- Israeli fiscal and economic conditions.
- Regional capital flows where reliable data is available.

### XAU/USD Engine

Monitor:

- Spot gold prices.
- Gold futures when available.
- US real yields.
- US Treasury yields.
- Dollar Index.
- Federal Reserve policy.
- Inflation expectations.
- Central bank gold purchases.
- Gold ETF flows.
- Commitment of Traders positioning where available.
- Geopolitical risk.
- Gold market volatility.

### BTC/USD Engine

Monitor:

- Bitcoin spot prices.
- Trading volume.
- Exchange order-book data.
- Open interest.
- Funding rates.
- Liquidations.
- Bitcoin ETF flows where reliable data is available.
- Exchange netflows.
- On-chain activity.
- Network metrics.
- Market capitalization.
- Crypto market sentiment.
- Bitcoin-specific news and regulatory developments.

On-chain and derivatives metrics must be optional modules with clear availability indicators. Do not fabricate missing values.

---

# 3. FORECASTING HORIZONS

The system must support:

| Horizon | Forecast purpose |
|---|---|
| 15 minutes | Short-term market movement |
| 1 hour | Intraday direction |
| 4 hours | Intraday trend |
| 24 hours | Daily forecast |
| 3 days | Short-term outlook |
| 7 days | Weekly outlook |
| 30 days | Monthly outlook |
| 90 days | Medium-term outlook |
| 180 days | Strategic outlook |

Not every model must support every horizon initially.

For each supported horizon, the system must produce:

- Expected direction.
- Expected return.
- Expected price range.
- Probability of bullish scenario.
- Probability of bearish scenario.
- Probability of neutral scenario.
- Confidence and data-quality indicators.
- Key supporting factors.
- Invalidation conditions.
- Forecast creation timestamp.
- Forecast expiry timestamp.

Probabilities must sum to 100%.

Forecast ranges must be statistically calibrated and must not be represented as guaranteed price targets.

---

# 4. SYSTEM ARCHITECTURE

Use a modular architecture with independent market and analytical services.

## 4.1 Recommended technology stack

| Component | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| UI | Tailwind CSS + component library |
| Backend | Python + FastAPI |
| Database | PostgreSQL |
| Time-series storage | TimescaleDB |
| Cache | Redis |
| Background jobs | Celery + Celery Beat |
| Quantitative analysis | NumPy + Pandas + SciPy |
| Machine Learning | Scikit-learn + XGBoost |
| Deep Learning | PyTorch, optional |
| Statistical models | Statsmodels + ARCH |
| Charts | TradingView Lightweight Charts |
| AI language model | Provider-independent LLM integration |
| News processing | Python ingestion and NLP pipeline |
| Notifications | Telegram Bot API + Email |
| Deployment | Docker Compose initially |
| Reverse proxy | Nginx |
| Testing | Pytest + Playwright |

Use a modular monolith initially rather than introducing unnecessary microservice complexity.

Separate modules through clear interfaces so they can be extracted into independent services later.

## 4.2 High-level architecture

Market Data Providers  
↓  
Data Ingestion Layer  
↓  
Data Validation and Normalization  
↓  
PostgreSQL / TimescaleDB  
↓  
Three Independent Market Engines  
↓  
Technical + Fundamental + Quantitative Analysis  
↓  
Forecasting and Scenario Engine  
↓  
AI Chief Analyst  
↓  
Paper Trading + Risk Management  
↓  
API and WebSocket Layer  
↓  
Next.js Dashboard + Alerts + Reports

## 4.3 Service isolation

Each market must have its own:

- Data configuration.
- Technical indicators.
- Forecast models.
- Forecast history.
- Signal history.
- Paper trading configuration.
- Performance metrics.

Shared services must include:

- Authentication.
- News ingestion.
- Economic calendar.
- Cross-asset analysis.
- Notification delivery.
- AI orchestration.
- Reporting.
- Audit logging.

---

# 5. MARKET DATA INFRASTRUCTURE

Market data is the foundation of the entire system.

## 5.1 Provider abstraction

Create a provider interface that prevents the application from depending on a single external vendor.

Required interface methods:

- get_latest_quote()
- get_historical_ohlcv()
- get_intraday_ohlcv()
- get_order_book()
- get_market_status()
- get_provider_status()

Optional capabilities:

- get_funding_rates()
- get_open_interest()
- get_liquidations()
- get_market_flows()
- get_onchain_metrics()

Not every provider implements every method.

## 5.2 Proposed data sources

### USD/ILS

Primary reference:
- Bank of Israel official exchange-rate publications and historical series.

Additional market data:
- A licensed Forex market-data provider.
- Intraday bid/ask feeds where available.

### XAU/USD

- A licensed metals or multi-asset market-data provider.
- Spot gold bid/ask.
- Historical OHLCV.
- Futures data as an additional source.

### BTC/USD

- Binance public market-data endpoints.
- CoinGecko as an independent reference and historical data provider.
- Additional derivatives and on-chain providers when required.

The system must support switching providers without rewriting analytical code.

## 5.3 Market data quality rules

Every observation must contain:

- Instrument identifier.
- Provider identifier.
- Observation timestamp in UTC.
- Reception timestamp in UTC.
- Open.
- High.
- Low.
- Close.
- Volume when available.
- Bid and ask when available.
- Data status.
- Provider latency.

Validation must detect:

- Missing candles.
- Duplicate candles.
- Invalid OHLC relationships.
- Outlier prices.
- Stale observations.
- Provider outages.
- Timestamp inconsistencies.
- Abnormal spreads.

Do not automatically fill missing prices with invented market observations.

If data is stale, display a warning and disable affected signals.

## 5.4 Market data normalization

Use a unified internal instrument format:

- USDILS
- XAUUSD
- BTCUSD

All stored timestamps must use UTC.

All user-facing times must be displayed in the configured timezone.

Keep provider-native symbols in a separate mapping table.

## 5.5 Update frequencies

Configure independent ingestion schedules.

Suggested initial targets:

| Data | Target frequency |
|---|---|
| BTC live quotes | WebSocket where available |
| BTC 1-minute candles | 1 minute |
| Gold live quotes | According to provider |
| USD/ILS live quotes | According to provider |
| Official exchange rates | On publication |
| Technical calculations | After each completed candle |
| News monitoring | Every 1–5 minutes |
| Economic calendar | Daily refresh plus event updates |
| Daily model evaluation | Once daily |

These are target schedules, not guarantees of provider availability.

---

# 6. DATABASE DESIGN

Use PostgreSQL with TimescaleDB for time-series data where appropriate.

The database must be migration-based and version-controlled.

## 6.1 Core tables

### users
- id
- name
- email
- password_hash
- role
- preferred_language
- timezone
- created_at
- updated_at

### instruments
- id
- symbol
- display_name
- asset_class
- base_currency
- quote_currency
- market_status
- enabled
- configuration_json

### market_providers
- id
- provider_name
- provider_type
- status
- configuration_json
- last_success_at
- last_error_at

### market_quotes
- id
- instrument_id
- provider_id
- bid
- ask
- mid
- last_price
- observed_at
- received_at
- data_quality_status

### market_candles
- instrument_id
- timeframe
- open_time
- close_time
- open
- high
- low
- close
- volume
- provider_id

Use a suitable composite key and time-series partitioning.

### technical_indicators
- id
- instrument_id
- timeframe
- timestamp
- indicator_name
- indicator_value
- indicator_parameters

### news_articles
- id
- provider_id
- external_id
- title
- content_summary
- original_url
- source_name
- language
- published_at
- collected_at
- credibility_score
- duplicate_group_id

### news_asset_impacts
- id
- article_id
- instrument_id
- sentiment
- expected_direction
- impact_score
- confidence
- explanation

### economic_events
- id
- country
- event_name
- event_category
- scheduled_at
- actual_value
- forecast_value
- previous_value
- importance
- source_url

### forecasts
- id
- instrument_id
- timeframe
- model_version
- issued_at
- expires_at
- reference_price
- predicted_price
- lower_bound
- upper_bound
- bullish_probability
- bearish_probability
- neutral_probability
- expected_return
- confidence_score
- data_quality_score
- explanation_json
- invalidation_conditions
- status

### forecast_evaluations
- id
- forecast_id
- evaluated_at
- actual_price
- absolute_error
- percentage_error
- direction_correct
- interval_covered
- probability_score

### trading_signals
- id
- instrument_id
- forecast_id
- signal_type
- entry_price
- stop_loss
- take_profit
- risk_reward_ratio
- confidence
- created_at
- expires_at
- status

### paper_accounts
- id
- user_id
- account_name
- initial_balance
- current_balance
- currency
- risk_profile
- created_at

### paper_orders
- id
- account_id
- instrument_id
- side
- order_type
- quantity
- requested_price
- simulated_fill_price
- spread_cost
- commission
- slippage
- status
- created_at

### paper_positions
- id
- account_id
- instrument_id
- side
- quantity
- average_entry_price
- current_price
- unrealized_pnl
- realized_pnl
- stop_loss
- take_profit
- opened_at
- closed_at

### paper_transactions
- id
- account_id
- transaction_type
- amount
- currency
- reference_id
- created_at

### alerts
- id
- user_id
- instrument_id
- alert_type
- condition_json
- enabled
- triggered_at

### model_registry
- id
- model_name
- model_version
- instrument_id
- horizon
- training_period
- validation_metrics
- deployment_status
- created_at

### system_audit_logs
- id
- user_id
- action
- entity_type
- entity_id
- details_json
- created_at

## 6.2 Database requirements

- Use foreign keys and indexes.
- Preserve historical forecasts.
- Never overwrite completed forecast records.
- Store model versions.
- Store original news URLs.
- Support retention policies for high-frequency market data.
- Use migrations for every schema change.
- Ensure financial calculations use appropriate decimal precision.
- Avoid floating-point arithmetic for monetary balances and order accounting.

---

# 7. TECHNICAL ANALYSIS ENGINE

Create a shared indicator library with instrument-specific configuration.

## 7.1 Required indicators

Trend:
- SMA 20, 50, 100, 200.
- EMA 9, 20, 50, 100, 200.
- ADX.
- Supertrend.

Momentum:
- RSI 14.
- MACD.
- Stochastic RSI.
- ROC.

Volatility:
- ATR.
- Bollinger Bands.
- Historical volatility.
- Average true range percentage.

Volume:
- OBV.
- VWAP where data supports it.
- Volume moving averages.

Price structure:
- Support and resistance.
- Swing highs and lows.
- Trendlines.
- Breakouts.
- Fibonacci retracements.
- Candlestick patterns.

## 7.2 Pattern recognition

Initially implement rule-based recognition for:

- Head and shoulders.
- Inverse head and shoulders.
- Double top.
- Double bottom.
- Triangles.
- Flags.
- Channels.
- Breakout and retest.

Every detected pattern must include:

- Detection timestamp.
- Instrument.
- Timeframe.
- Pattern type.
- Relevant price boundaries.
- Confirmation status.
- Invalidation condition.

Pattern recognition must be tested against historical data.

## 7.3 Technical analysis output

Produce structured JSON, not only natural-language text.

Example:

```json
{
  "instrument": "USDILS",
  "timeframe": "4h",
  "trend": "bullish",
  "momentum": "positive",
  "volatility": "moderate",
  "support_levels": [],
  "resistance_levels": [],
  "indicators": {},
  "patterns": [],
  "invalidations": [],
  "calculated_at": "UTC_TIMESTAMP"
}
```

The values above are an output schema example, not an actual market analysis.

---

# 8. FUNDAMENTAL AND MACROECONOMIC ENGINE

## 8.1 Economic indicators

Implement a standardized economic data model.

For the United States:
- Federal Funds Rate.
- CPI.
- Core CPI.
- PCE.
- Core PCE.
- Unemployment.
- Nonfarm Payrolls.
- GDP.
- Treasury yields.
- Real yields.
- DXY.

For Israel:
- Bank of Israel policy rate.
- CPI.
- Inflation expectations.
- GDP.
- Unemployment.
- Fiscal indicators.
- Trade balance.
- Foreign currency reserves.
- Current account.

For gold:
- Central bank gold reserves and purchases.
- Gold ETF flows.
- Futures positioning.

For Bitcoin:
- ETF flows.
- Funding rates.
- Open interest.
- Market liquidity.
- Network activity.

## 8.2 Event impact engine

For each event:

1. Retrieve the event.
2. Validate the source.
3. Compare actual, forecast, and previous values.
4. Determine which instruments are affected.
5. Calculate the historical relationship where data permits.
6. Estimate the possible impact.
7. Produce a confidence-qualified explanation.

Never assume that stronger economic data always strengthens a currency. The reaction depends on market expectations, interest-rate implications, positioning, and context.

---

# 9. NEWS INTELLIGENCE ENGINE

## 9.1 News collection

Collect news in Arabic and English.

Required topics:

- US economy.
- Israeli economy.
- Middle East geopolitics.
- Federal Reserve.
- Bank of Israel.
- Gold markets.
- Bitcoin markets.
- Financial regulation.
- Global financial risk.

Use reputable sources and official announcements.

## 9.2 News processing pipeline

News source
→ Article retrieval
→ Language detection
→ Duplicate detection
→ Source verification
→ Entity extraction
→ Instrument relevance
→ Sentiment analysis
→ Impact assessment
→ Historical comparison
→ AI explanation.

## 9.3 News scoring

Each article should have:

- Source credibility.
- Relevance to instrument.
- Expected direction.
- Estimated impact.
- Confidence.
- Time sensitivity.
- Confirmation status.

Do not confuse sentiment with price direction.

A negative headline may already be priced into the market.

## 9.4 Source traceability

Every news-based AI explanation must link to the original source.

The AI must distinguish:

- Verified facts.
- Reported claims.
- Analyst opinions.
- Speculation.
- Unconfirmed breaking news.

---

# 10. QUANTITATIVE FORECASTING ENGINE

Build multiple models and compare them.

## 10.1 Initial model portfolio

Statistical:
- ARIMA.
- SARIMAX.
- GARCH.

Machine Learning:
- Random Forest.
- XGBoost.
- LightGBM where appropriate.

Deep Learning:
- LSTM as an experimental model.
- Additional sequence models only after validation.

Simulation:
- Monte Carlo.

Baseline:
- Random walk.
- Last-value persistence.
- Simple historical volatility forecast.

## 10.2 Model-specific configuration

Models must be trained and evaluated independently by:

- Instrument.
- Timeframe.
- Forecast horizon.
- Market regime.

Do not assume a model trained on Bitcoin can forecast USD/ILS effectively.

## 10.3 Feature engineering

Potential features:

- Lagged returns.
- Rolling volatility.
- Moving averages.
- RSI.
- MACD.
- Volume changes.
- Spread.
- DXY.
- Treasury yields.
- Economic surprise indicators.
- News sentiment.
- Cross-asset returns.
- Funding rates for BTC.
- Gold-specific flows.

Only use features that are available at the forecast creation timestamp.

## 10.4 Model validation

Use:

- Chronological train/validation/test splits.
- Walk-forward validation.
- Out-of-sample evaluation.
- Purged or embargoed validation where overlapping labels require it.
- Leakage detection.
- Hyperparameter tuning restricted to training and validation data.

Do not randomly shuffle time-series observations.

## 10.5 Ensemble forecasting

Create an ensemble that combines model outputs.

The ensemble must:

1. Evaluate model performance.
2. Evaluate forecast horizon.
3. Evaluate current market regime.
4. Assign validated weights.
5. Generate an ensemble distribution.
6. Calibrate scenario probabilities.
7. Compare against baseline models.

Do not use arbitrary fixed weights presented as scientific probabilities.

If no model demonstrates out-of-sample value, label the forecast experimental.

---

# 11. CENTRAL AI CHIEF ANALYST

The central AI analyst is responsible for interpreting structured results.

It must not independently invent technical indicators or market prices.

## 11.1 Inputs

- Latest verified quotes.
- Technical analysis results.
- Quantitative model outputs.
- Economic calendar.
- News analysis.
- Cross-asset relationships.
- Data quality status.
- Historical model performance.

## 11.2 Outputs

For every asset:

- Executive market summary.
- Current market regime.
- Technical interpretation.
- Fundamental interpretation.
- News impact.
- Forecast scenarios.
- Key price levels.
- Risk assessment.
- Conflicting evidence.
- Conditions that invalidate the analysis.

## 11.3 AI response rules

The AI must:

- Separate facts from opinions.
- Reference the date and time of information.
- Explain disagreements between models.
- Show missing information.
- Avoid unsupported confidence.
- Refuse to generate a numerical forecast when data is insufficient.
- Never promise profits.
- Never describe a forecast as certain.

## 11.4 Structured response contract

```json
{
  "instrument": "XAUUSD",
  "as_of": "UTC_TIMESTAMP",
  "market_regime": "range",
  "overall_bias": "neutral",
  "scenarios": {
    "bullish": {
      "probability": 30,
      "target_range": null,
      "conditions": []
    },
    "neutral": {
      "probability": 45,
      "target_range": null,
      "conditions": []
    },
    "bearish": {
      "probability": 25,
      "target_range": null,
      "conditions": []
    }
  },
  "supporting_evidence": [],
  "contradicting_evidence": [],
  "risks": [],
  "data_quality": "verified",
  "forecast_expiry": "UTC_TIMESTAMP"
}
```

This is a schema example only.

---

# 12. CROSS-ASSET INTELLIGENCE

Build a separate engine to study relationships between all three assets.

## 12.1 Required analysis

- USD/ILS versus DXY.
- XAU/USD versus DXY.
- XAU/USD versus real yields.
- BTC/USD versus DXY.
- BTC/USD versus gold.
- BTC/USD versus equity market indicators where available.
- Rolling correlations.
- Volatility relationships.
- Event-driven co-movement.

## 12.2 Important restrictions

- Correlation is not causation.
- Use multiple rolling windows.
- Detect changes in correlation.
- Avoid assuming that historical correlations remain stable.
- Display sample size and data period.
- Include confidence or uncertainty indicators.

## 12.3 Cross-market dashboard

Display:

- Correlation matrix.
- Rolling correlation charts.
- Market regime comparison.
- Relative strength.
- Volatility comparison.
- Important divergence alerts.

---

# 13. PAPER TRADING ENGINE

This is a mandatory core module.

The system must support simulated trading only.

No real exchange trading credentials, real-money order endpoints, or live execution functions are permitted in version 1.

## 13.1 Account creation

Allow users to create simulated accounts.

Initial configurable balances:
- USD.
- ILS.
- Optional additional account currencies.

Allow separate paper accounts for:

- Forex.
- Gold.
- Bitcoin.
- Combined portfolio.

## 13.2 Order types

Support:

- Market orders.
- Limit orders.
- Stop orders.
- Stop-loss.
- Take-profit.

Orders must be simulated using available market prices and documented fill rules.

## 13.3 Execution simulation

Account for:

- Bid/ask spread.
- Slippage.
- Commission.
- Market liquidity.
- Trading hours.
- Gaps.
- Partial fills where realistic.
- Financing and swap costs where applicable.

For BTC, simulate continuous 24/7 trading.

For USD/ILS and gold, use provider-defined trading sessions and market closures.

Do not treat a candle's closing price as guaranteed executable liquidity.

## 13.4 Position management

Display:

- Entry price.
- Current mark price.
- Quantity.
- Direction.
- Unrealized P&L.
- Realized P&L.
- Stop-loss.
- Take-profit.
- Fees.
- Holding time.
- Maximum favorable excursion.
- Maximum adverse excursion.

## 13.5 Portfolio risk

Calculate:

- Total equity.
- Available cash.
- Exposure by asset.
- Risk per position.
- Drawdown.
- Win rate.
- Profit factor.
- Sharpe ratio where statistically meaningful.
- Maximum consecutive losses.

## 13.6 Paper trading modes

Mode A: Manual simulated trading.

Mode B: Signal-based simulated trading.

Mode C: Strategy backtesting.

All trades must be marked clearly as simulated.

---

# 14. IMPORTER ADVISOR

Build a dedicated business-oriented USD/ILS advisory module.

The module helps users plan currency purchases for supplier payments and imports.

## 14.1 User inputs

- Invoice amount in USD.
- Payment due date.
- Current executable USD/ILS buy rate.
- Available ILS balance.
- Desired risk tolerance.
- Transfer and conversion fees.
- Optional partial-payment schedule.

## 14.2 Analysis

Calculate:

- Cost of purchasing the full amount now.
- Cost under different future exchange-rate scenarios.
- Cost of purchasing in installments.
- Potential cost of waiting.
- Worst-case exposure.
- Break-even rate.
- Currency shortfall.

## 14.3 Scenario simulation

Example invoice:

50,000 USD.

| Exchange rate | Invoice cost |
|---|---:|
| 3.10 | 155,000 ILS |
| 3.20 | 160,000 ILS |
| 3.30 | 165,000 ILS |
| 3.50 | 175,000 ILS |
| 3.80 | 190,000 ILS |
| 4.00 | 200,000 ILS |

All calculations must be dynamic.

## 14.4 Advisory output

The advisor may compare:

- Purchase now.
- Purchase in installments.
- Wait with an explicit risk analysis.

It must not guarantee the cheapest future purchase price.

It must distinguish a forecast from a currency hedge or guaranteed exchange rate.

---

# 15. DASHBOARD AND USER EXPERIENCE

Create a professional financial terminal interface.

The design should be modern, clean, information-dense, responsive, and suitable for desktop and mobile.

## 15.1 Main navigation

1. Global Overview.
2. Market Monitor.
3. USD/ILS Intelligence.
4. Gold Intelligence.
5. Bitcoin Intelligence.
6. AI Forecast Center.
7. Cross-Asset Analysis.
8. News Intelligence.
9. Economic Calendar.
10. Technical Analysis.
11. Trading Signals.
12. Paper Trading.
13. Portfolio Analytics.
14. Importer Advisor.
15. Backtesting.
16. Model Performance.
17. Alerts Center.
18. Reports.
19. Data Sources.
20. System Settings.

## 15.2 Global Overview

Show:

- Latest price of each asset.
- Daily percentage change.
- Data freshness.
- Market status.
- Market direction.
- Current volatility.
- Latest forecast.
- Most important news.
- Upcoming economic events.
- Active alerts.
- Paper portfolio summary.

## 15.3 Asset detail page

Each asset page must include:

- Main interactive chart.
- Multiple timeframes.
- Candlesticks.
- Technical indicators.
- Support/resistance.
- Forecast ranges.
- Scenario probabilities.
- Technical analysis.
- Fundamental analysis.
- News timeline.
- Market statistics.
- Historical forecasts.
- Paper trading controls.

## 15.4 Forecast Center

Provide a unified comparison of all assets and forecast horizons.

Include:

- Price projection chart.
- Forecast confidence intervals.
- Scenario probability visualization.
- Model disagreement.
- Forecast history.
- Invalidation levels.
- Data-quality warnings.

## 15.5 Language

Support Arabic and English.

Arabic must use RTL layout.

English must use LTR layout.

All market symbols, numbers, and financial calculations must remain unambiguous across both languages.

---

# 16. ALERTS AND AUTOMATED REPORTS

## 16.1 Alert types

- Price threshold.
- Percentage movement.
- Technical breakout.
- Support/resistance breach.
- Forecast revision.
- Probability shift.
- Volatility spike.
- Major news event.
- Economic event reminder.
- Data provider outage.
- Paper trade execution.

## 16.2 Delivery

- Dashboard notifications.
- Telegram.
- Email.

Allow per-user configuration.

## 16.3 Automated reports

Daily:
- Market overview.
- Technical outlook.
- News summary.
- Economic events.
- Forecast scenarios.
- Active risks.

Weekly:
- Market performance.
- Model performance.
- Forecast accuracy.
- Trading simulation performance.

Monthly:
- Model ranking.
- Regime analysis.
- Portfolio simulation review.
- Forecast calibration report.

Reports must include data timestamps and source links.

---

# 17. FORECAST ACCOUNTABILITY AND MODEL PERFORMANCE

This module is essential.

Every forecast must be immutable after issuance, except for adding evaluation results.

## 17.1 Evaluation metrics

Forecast accuracy:
- MAE.
- RMSE.
- MAPE where appropriate and numerically valid.
- Directional accuracy.

Probability quality:
- Brier Score.
- Log Loss.
- Calibration curves.

Interval quality:
- Interval coverage.
- Interval width.
- Pinball loss for quantile forecasts.

Trading simulation:
- Net P&L.
- Win rate.
- Profit factor.
- Maximum drawdown.
- Sharpe ratio.
- Exposure.
- Trading costs.

## 17.2 Model comparison

Compare:

- Every model.
- Every instrument.
- Every horizon.
- Every market regime.

A model must not be promoted simply because it performed well on training data.

## 17.3 Forecast audit

Preserve:

- Original forecast.
- Model version.
- Input data snapshot or reproducible data references.
- Creation timestamp.
- Evaluation timestamp.
- Actual outcome.
- Evaluation methodology.

Never silently revise a historical forecast.

---

# 18. API DESIGN

Use REST APIs for core operations and WebSockets for live updates.

Suggested API groups:

## Authentication
- POST /api/v1/auth/login
- POST /api/v1/auth/logout
- GET /api/v1/auth/me

## Instruments
- GET /api/v1/instruments
- GET /api/v1/instruments/{symbol}

## Market data
- GET /api/v1/markets/{symbol}/quote
- GET /api/v1/markets/{symbol}/candles
- GET /api/v1/markets/{symbol}/statistics

## Analysis
- GET /api/v1/analysis/{symbol}/technical
- GET /api/v1/analysis/{symbol}/fundamental
- GET /api/v1/analysis/{symbol}/news

## Forecasts
- GET /api/v1/forecasts
- GET /api/v1/forecasts/{id}
- GET /api/v1/forecasts/{symbol}/latest
- GET /api/v1/forecasts/{symbol}/history

## Signals
- GET /api/v1/signals
- GET /api/v1/signals/{id}

## Paper trading
- GET /api/v1/paper/accounts
- POST /api/v1/paper/accounts
- GET /api/v1/paper/accounts/{id}/portfolio
- POST /api/v1/paper/orders
- DELETE /api/v1/paper/orders/{id}
- GET /api/v1/paper/positions
- POST /api/v1/paper/positions/{id}/close
- GET /api/v1/paper/performance

## Importer advisor
- POST /api/v1/importer/scenarios
- POST /api/v1/importer/compare-strategies
- GET /api/v1/importer/history

## Reports
- GET /api/v1/reports/daily
- GET /api/v1/reports/weekly
- GET /api/v1/reports/monthly

## Administration
- GET /api/v1/admin/providers
- GET /api/v1/admin/jobs
- GET /api/v1/admin/models
- GET /api/v1/admin/system-health

All endpoints must use typed schemas, input validation, pagination, authentication, and structured errors.

---

# 19. SECURITY AND RELIABILITY

Required:

- Secure authentication.
- Password hashing.
- Role-based access control.
- API rate limiting.
- Secret management through environment variables.
- HTTPS.
- Database backups.
- Audit logs.
- Input validation.
- Protection against prompt injection in retrieved news.
- Provider request timeouts.
- Retry policies with exponential backoff.
- Job idempotency.
- Monitoring and health checks.
- Error reporting.

Never expose API keys to frontend code.

Do not allow news articles or external provider responses to execute instructions inside the AI system.

Treat external content as untrusted data.

## 19.1 Paper trading isolation

Version 1 must not contain active real-money execution.

- No real trading credentials.
- No real order submission.
- No wallet withdrawal functionality.
- No automatic external account access.
- No live broker execution adapters.

Paper trading must use an internal simulation engine.

---

# 20. RECOMMENDED PROJECT STRUCTURE

```
gmi/
│
├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   ├── markets/
│   │   ├── forecasts/
│   │   ├── analysis/
│   │   ├── news/
│   │   ├── calendar/
│   │   ├── paper-trading/
│   │   ├── portfolio/
│   │   ├── importer-advisor/
│   │   ├── performance/
│   │   └── settings/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   ├── types/
│   └── locales/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── services/
│   │   ├── providers/
│   │   ├── ingestion/
│   │   ├── indicators/
│   │   ├── analysis/
│   │   ├── forecasting/
│   │   ├── news/
│   │   ├── economics/
│   │   ├── cross_asset/
│   │   ├── paper_trading/
│   │   ├── importer_advisor/
│   │   ├── notifications/
│   │   ├── reports/
│   │   └── tasks/
│   ├── migrations/
│   └── tests/
│
├── ml/
│   ├── datasets/
│   ├── features/
│   ├── models/
│   ├── training/
│   ├── validation/
│   ├── evaluation/
│   ├── backtesting/
│   └── artifacts/
│
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   ├── monitoring/
│   └── backups/
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── database/
│   ├── models/
│   ├── operations/
│   └── decisions/
│
├── scripts/
├── docker-compose.yml
├── .env.example
├── README.md
└── CHANGELOG.md
```

The structure may be refined during implementation, but separation of responsibilities is mandatory.

---

# 21. IMPLEMENTATION ROADMAP

Estimated delivery plan: 12–16 weeks for an initial production-quality system, subject to team size, data licensing, and provider availability.

## Phase 1 – Foundation
Week 1–2

- Repository setup.
- Architecture.
- Database.
- Authentication.
- Instrument configuration.
- Docker environment.
- Logging and monitoring.

Deliverable: Running application foundation.

## Phase 2 – Market data
Week 3–4

- USD/ILS data.
- Gold data.
- Bitcoin data.
- Provider adapters.
- Historical imports.
- Data quality validation.
- Live market updates.

Deliverable: Reliable multi-asset market data layer.

## Phase 3 – Analysis
Week 5–6

- Technical indicators.
- Charting.
- Economic calendar.
- News ingestion.
- News relevance and sentiment.
- Fundamental analysis.

Deliverable: Three independent analytical engines.

## Phase 4 – Forecasting
Week 7–9

- Baseline models.
- Statistical models.
- Machine learning.
- Feature engineering.
- Walk-forward validation.
- Forecast ensemble.
- Forecast storage and evaluation.

Deliverable: Measurable forecasting system.

## Phase 5 – AI Intelligence
Week 10

- Central AI analyst.
- Structured explanations.
- Scenario generation.
- News synthesis.
- Cross-asset intelligence.

Deliverable: AI-powered analytical reports.

## Phase 6 – Paper trading and importer advisor
Week 11–12

- Paper accounts.
- Simulated orders.
- Positions.
- Risk calculations.
- Performance.
- Importer currency scenarios.

Deliverable: Functional simulation environment.

## Phase 7 – Dashboard and notifications
Week 13–14

- Complete dashboard.
- Arabic/English support.
- Telegram.
- Reports.
- Alert management.

Deliverable: User-ready platform.

## Phase 8 – Hardening and acceptance
Week 15–16

- Security testing.
- Data reliability testing.
- Forecast validation.
- Load testing.
- Backup recovery.
- User acceptance testing.

Deliverable: Release candidate.

---

# 22. TESTING AND ACCEPTANCE CRITERIA

The project is not complete merely because the pages render.

The following criteria must be demonstrated.

## Market data

- All three instruments retrieve data.
- Each observation has source and timestamp.
- Stale data is detected.
- Missing candles are detected.
- Provider outages do not crash the application.

## Technical analysis

- Indicator calculations are independently tested.
- Calculations match reference datasets within documented tolerances.
- Different timeframes use correct candle boundaries.
- No future candles leak into past analysis.

## Forecasting

- Forecasts are saved before evaluation.
- Walk-forward validation works.
- Baselines are included.
- Probability calibration is measured.
- Every model has a version.
- Every forecast has an expiry.
- Poor-quality data disables unsupported predictions.

## Paper trading

- Simulated balances reconcile.
- Fees and spreads are applied.
- Orders follow documented fill rules.
- Stop-loss and take-profit behavior is tested.
- Positions and P&L are reproducible.
- No real-money order execution is possible.

## Security

- API keys are never returned to the frontend.
- Unauthorized users cannot access other accounts.
- Secrets are not committed to Git.
- External news content cannot execute AI instructions.

## User interface

- All pages support Arabic and English.
- RTL and LTR layouts work.
- Responsive behavior is tested.
- Data freshness is visible.
- Forecast uncertainty is visible.
- Simulated trades are clearly labeled.

---

# 23. DOCUMENTATION DELIVERABLES

Claude Code must maintain these documents throughout development:

1. README.md – Installation and project overview.
2. ARCHITECTURE.md – System architecture.
3. DATABASE.md – Schema and relationships.
4. DATA_SOURCES.md – Providers, coverage, licensing, and limitations.
5. FORECASTING.md – Models, features, training, and validation.
6. PAPER_TRADING.md – Simulation rules and accounting.
7. API_REFERENCE.md – API contracts.
8. SECURITY.md – Security architecture.
9. DEPLOYMENT.md – Production deployment.
10. OPERATIONS.md – Monitoring and maintenance.
11. CHANGELOG.md – Implemented changes.
12. IMPLEMENTATION_STATUS.md – Completed and pending work.

---

# 24. CLAUDE CODE DEVELOPMENT RULES

Claude Code must follow these rules:

1. Read this document completely before writing code.
2. Create a detailed implementation plan.
3. Inspect the repository before changing files.
4. Never assume a feature has been implemented.
5. Work in small, verifiable phases.
6. Do not create fake market data for production.
7. Mock data is permitted only in explicitly labeled development fixtures.
8. Never hardcode current prices.
9. Never hardcode model performance.
10. Do not implement untested financial calculations.
11. Write unit and integration tests for every critical module.
12. Use typed schemas and clear interfaces.
13. Keep secrets in environment variables.
14. Keep all market timestamps in UTC.
15. Never mix simulated trading with real trading.
16. Never silently alter completed forecasts.
17. Update documentation with every major implementation.
18. Run tests after each meaningful change.
19. Report incomplete features honestly.
20. Do not mark a phase complete without satisfying its acceptance criteria.

## Required workflow for every phase

A. Explain the implementation plan.

B. Identify the files to create or modify.

C. Implement the phase.

D. Run automated tests.

E. Fix all failures.

F. Update documentation.

G. Report:
- Completed features.
- Files changed.
- Tests executed.
- Test results.
- Remaining issues.
- External API dependencies.
- Required configuration.

Do not proceed to the next phase if a critical acceptance criterion fails.

---

# 25. INITIAL CLAUDE CODE MASTER PROMPT

Use the following prompt when starting development:

You are the lead software architect and senior engineering team responsible for building GLOBAL MARKET INTELLIGENCE.

Your task is to implement a professional multi-asset AI financial intelligence and paper trading platform according to the complete Software Requirements Specification supplied in the project documentation.

The three supported instruments are:

- USDILS
- XAUUSD
- BTCUSD

All three have equal product priority.

The system must provide:

- Market data collection.
- Technical analysis.
- Fundamental and macroeconomic analysis.
- News intelligence.
- Quantitative forecasting.
- AI-assisted interpretation.
- Cross-asset analysis.
- Forecast accountability.
- Paper trading.
- Importer currency advisory.
- Performance evaluation.
- Notifications.
- Arabic and English dashboard.

IMPORTANT:

This is a real financial software project.

Do not create a decorative dashboard that displays fabricated market prices or fictional forecasting results.

Build real data integrations, verified calculations, reproducible models, persistent forecasts, and a working simulated trading engine.

All real-money trading is prohibited in version 1.

Your first assignment is NOT to start implementing the entire system.

First:

1. Inspect the repository.
2. Read the complete requirements.
3. Identify technical dependencies.
4. Produce a detailed architecture plan.
5. Create a database design.
6. Identify required external APIs and their limitations.
7. Create an implementation roadmap.
8. Identify risks, unknowns, and licensing requirements.
9. Create a phase-by-phase task breakdown.
10. Present the plan for review.

After the initial review, begin implementation phase by phase.

Never claim that a feature works unless it has been implemented and tested.

The ultimate objective is a reliable financial intelligence system whose forecasting performance can be measured objectively over time.

---

# END OF SPECIFICATION

**Project status:** Approved architecture and requirements.  
**Next status:** Repository inspection and technical planning.  
**Release target:** GMI Version 1.0 – Three Markets, AI Forecasting, and Paper Trading.
