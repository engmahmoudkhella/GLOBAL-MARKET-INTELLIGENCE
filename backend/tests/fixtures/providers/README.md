# Provider response fixtures – DEVELOPMENT FIXTURES, NOT MARKET DATA

These files are **hand-written from the providers' documented response formats**. They are
**not recorded live responses**: the build sandbox cannot reach Coinbase or the Bank of Israel.
All numbers are illustrative test values and must never be shown as market data.

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
