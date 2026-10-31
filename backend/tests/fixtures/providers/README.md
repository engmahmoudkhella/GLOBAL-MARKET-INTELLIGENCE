# Provider response fixtures – DEVELOPMENT FIXTURES, NOT LIVE MARKET DATA

Two kinds of fixtures live here, distinguished by file name and by the table below:

* **doc-derived**: hand-written from the provider's documented format, with illustrative numbers.
  Not recorded live. The build sandbox cannot reach the providers.
* **recorded** (`*.recorded-YYYY-MM-DD.json`): real responses captured by the owner, kept verbatim.
  They are historical snapshots used only to test parsing and rules, never shown as current prices.

Before relying on the adapters in production, run on the VPS:

    uv run python ../scripts/check_provider_contracts.py

which fetches the live endpoints and parses them with the same adapters. If a format differs,
the adapter raises `ProviderDataError` (it never guesses). Fix the parser, then replace the fixture
with a recorded response and note the recording date here.

| File | Source format | Status |
|---|---|---|
| coinbase_ticker.json | GET /products/BTC-USD/ticker | written from docs, unverified |
| coinbase_candles.json | GET /products/BTC-USD/candles | written from docs, unverified |
| coinbase_book.json | GET /products/BTC-USD/book?level=2 | written from docs, unverified |
| coinbase_product.json | GET /products/BTC-USD | written from docs, unverified |
| coinbase_time.json | GET /time | written from docs, unverified |
| boi_exchange_rates.json | GET boi.org.il/PublicApi/GetExchangeRates | written from docs, unverified |
| boi_rer_usd_ils.csv | BoI SDMX EXR RER_USD_ILS, format=csv | written from docs, unverified |
| twelvedata_quote_usdils.recorded-2026-10-31.json | GET /quote?symbol=USD/ILS | **recorded live 2026-10-31 ~10:27 UTC, free Basic key** (owner) |
| twelvedata_quote_xauusd.recorded-2026-10-31.json | GET /quote?symbol=XAU/USD | **recorded live 2026-10-31 ~10:27 UTC, free Basic key** (owner) |
| twelvedata_time_series_1min.json | GET /time_series?interval=1min&timezone=UTC | written from docs, unverified |
| twelvedata_error_credits.json | error body (credits exhausted) | written from docs, unverified |
| twelvedata_api_usage.json | GET /api_usage | written from docs, unverified |
