# Provider response fixtures – DEVELOPMENT FIXTURES, NOT LIVE MARKET DATA

Two kinds of fixtures live here, distinguished by file name and by the table below:

* **doc-derived**: hand-written from the provider's documented format, with illustrative numbers.
  Not recorded live. The build sandbox cannot reach the providers.
* **recorded** (`*.recorded-YYYY-MM-DD*.json`): real responses captured by the owner, kept verbatim.
  They are historical snapshots used only to test parsing and rules, never shown as current prices.
* **browser copy** (`*.browser-copy-*`): structure copied from a browser view. **Not byte-exact.**
  Use for structure only; re-record raw from the VPS.

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
| twelvedata_quote_usdils.recorded-2026-10-31.json | GET /quote?symbol=USD/ILS | **recorded live 2026-10-31 ~10:27 UTC, free Basic key** (owner) |
| twelvedata_quote_xauusd.recorded-2026-10-31.json | GET /quote?symbol=XAU/USD | **recorded live 2026-10-31 ~10:27 UTC, free Basic key** (owner) |
| boi_exchange_rates.recorded-2026-10-31.json | GET www.boi.org.il/PublicApi/GetExchangeRates | **recorded live 2026-10-31 via browser** (owner, Gaza, ~10:56–10:59 UTC) |
| boi_sdmx_rer_usd_ils.browser-copy-2026-10-31.xml | GET edge.boi.org.il/.../RER_USD_ILS?startperiod=2026-10-20 (SDMX-ML 2.1 XML) | **browser copy, not byte-exact**; Series/Obs as copied, wrapper reconstructed |
| coinbase_ticker.recorded-2026-10-31a.json / …b.json | GET /products/BTC-USD/ticker (two calls) | **recorded live 2026-10-31 via browser** |
| coinbase_candles_1h.recorded-2026-10-31.partial.json | GET /products/BTC-USD/candles?granularity=3600 | **recorded live 2026-10-31 via browser**, first 3 rows of the 350-row response (350 consecutive hours, no gaps) only |
| twelvedata_time_series_1h_no_tz.recorded-2026-10-31.json | GET /time_series?symbol=USD/ILS&interval=1h&outputsize=5 **without timezone** | **recorded live 2026-10-31 via browser**; datetimes are NOT UTC |
| twelvedata_api_usage.recorded-2026-10-31.json | GET /api_usage | **recorded live 2026-10-31 via browser** (Basic plan) |
| twelvedata_time_series_1min.json | GET /time_series?interval=1min&timezone=UTC | written from docs, unverified |
| twelvedata_error_credits.json | error body (credits exhausted) | written from docs, unverified |
| coingecko_simple_price.json | GET /api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_last_updated_at=true | written from docs, unverified |
| coingecko_ping.json | GET /api/v3/ping | written from docs, unverified |
| binance_book_ticker.json | GET data-api.binance.vision/api/v3/ticker/bookTicker?symbol=BTCUSDT | written from docs, unverified |
| binance_klines_1m.json | GET /api/v3/klines?symbol=BTCUSDT&interval=1m | written from docs, unverified |
| binance_time.json | GET /api/v3/time | written from docs, unverified |
