# GMI – Data Sources, Coverage, Licensing and Limitations

**Status (2026-10-31):** Coinbase and Bank of Israel adapters are **implemented and tested against fixtures written from their documentation**. They have **not yet been verified against live responses**, because the build sandbox cannot reach them; run `scripts/check_provider_contracts.py` on the VPS. The Twelve Data adapter is **implemented**. Its `/quote` contract is **verified against the owner's recorded live responses** (2026-10-31), while `/time_series` and `/api_usage` are still documentation-based. CoinGecko and Binance are not implemented yet. Terms, rate limits and pricing **must be re-verified
against each provider's current documentation and terms of service before integration**. They change often and are
listed here only as planning assumptions.

| Provider | Instruments / data | Access | Licensing notes | Known limitations | Status |
|---|---|---|---|---|---|
| Bank of Israel | USD/ILS representative rate, BoI policy rate, Israeli series | Public website / series API | Public data. Attribution required. | Once per business day. **Not an executable price.** No intraday data. Stored in `official_reference_rates`, never as quotes. | **Adapter implemented** (`app/providers/boi.py`): latest via PublicApi, history via SDMX `RER_USD_ILS`. Live contract unverified. |
| Israel CBS | Israeli CPI, GDP, unemployment, trade | Public | Public data | Release formats vary | Planned (Phase 4) |
| **Twelve Data – Grow** (individual plan) | **USD/ILS and XAU/USD** quotes and OHLCV | Paid individual plan, API key | Basic/Grow: **personal, non-commercial use only. No display or redistribution to third parties.** This fits the single-user deployment. | Per-minute API credit limit (no daily cap on Grow). Quotes are indicative, not a bank's executable rate. See **Twelve Data contract notes** below. | **Adapter implemented** (`app/providers/twelvedata.py`). Coverage of USD/ILS and XAU/USD **confirmed** (G1/G2, owner test 2026-10-31). **Free Basic key for development only** (8 credits/min, 800/day, non-display). **Switch to Grow $29 (55 credits/min) before live ingestion on the VPS.** |
| CME/COMEX via vendor | Gold futures | Paid | Exchange fees | Optional | Optional |
| **Coinbase Exchange** | **BTC-USD primary**: ticker, candles, order book, trades, WebSocket feed | Public endpoints, no key (`api.exchange.coinbase.com`) | Coinbase **Market Data Terms of Use** apply. Personal-use wording **not yet verified (G5)**. | About 10 req/s per IP (burst 15). Servers reported in AWS us-east-1. Reachability from EU VPS to test (G6). Candles endpoint returns at most 300 buckets per request. Granularities 1m/5m/15m/1h/6h/1d only (**no 4h**, which will be derived from 1h). | **Adapter implemented** (`app/providers/coinbase.py`): ticker, candles, L2 book, product status, server time. Live contract unverified. |
| Binance | **BTCUSDT secondary series** (separate from BTCUSD); futures funding rate and open interest | Public endpoints, no key; `data-api.binance.vision` spot-only mirror | Binance terms of use apply | **EU services limited since July 2026 (G7)**. HTTP 451 in blocked regions. Quote currency is **USDT and is never relabelled as USD**. | Optional secondary (Phase 2) |
| **CoinGecko – Demo** | BTC/USD independent reference price, market cap, history | Free Demo API key | **Attribution required**: a "Powered by CoinGecko API" link in the UI | 30 calls/min, 10,000 calls/month | **Selected** (Phase 2) |
| FRED / ALFRED (St. Louis Fed) | Fed funds, Treasury yields, real yields (TIPS), CPI, PCE, Broad Dollar Index | Free API key | Public. Some series carry third-party copyright notices. | Data revisions. Use ALFRED vintages for point-in-time. | Planned (Phase 4) |
| BLS, BEA, US Treasury | CPI, NFP, unemployment, GDP, PCE, yield curve | Free (keys for BLS/BEA) | Public | — | Planned (Phase 4) |
| ICE DXY | US Dollar Index | Licensed | Proprietary | — | **Not used in v1** (D4). The Fed Broad Dollar Index (FRED `DTWEXBGS`) is used instead and labelled as such. |
| CFTC | Commitments of Traders (gold) | Free | Public | Weekly, lagged | Planned (Phase 4) |
| World Gold Council | ETF flows, central bank purchases | Website | Terms restrict automated reuse | — | Manual / licence required |
| Coinglass / Glassnode / CryptoQuant | Liquidations, on-chain, exchange netflows, ETF flows | Paid | Commercial licences | Optional modules | Optional |
| Official RSS/APIs (Fed, Bank of Israel, BLS, BEA, Treasury, SEC, Israel CBS) and reputable Arabic and English outlets' RSS | News EN/AR | Free | **Store title, summary and URL only, never full text** (D6) | Coverage and quality vary. The outlet list is maintained in config. | Planned (Phase 4) |
| Telegram Bot API | Alert delivery | Free | — | Per-chat rate limits | Planned (Phase 8) |
| Anthropic API (Claude) | AI Chief Analyst narrative (D5) | Paid per token, API key (server only) | Anthropic commercial terms | Cost and latency. Behind the `LLMClient` adapter. | Planned (Phase 6) |

## Twelve Data contract notes (from recorded `/quote` responses, 2026-10-31, free Basic key)

| Observation | Handling |
|---|---|
| All numeric fields are JSON **strings** | Parsed strictly to `Decimal`. A number, non-numeric string or non-positive price is rejected (`ProviderDataError`). |
| **No `bid`/`ask`** in `/quote` | `last_price` = `close`, `price_type = last`. The bid/ask columns stay nullable. If a later plan or endpoint provides them, mid is preferred automatically. |
| `last_quote_at` (epoch s) | Used as `observed_at`. Responses without it are rejected. |
| `is_market_open` reported **true on Saturday 10:27 UTC** | **Never trusted.** It is kept only in the issue details for audit. Our session calendar decides. Out-of-session quotes are stored as `suspect: out_of_session` and excluded from everything. |
| `timestamp` = **2026-10-30 20:00 UTC = 16:00 New York (EDT)** | This is the provider's **daily bar start**, which is provider-defined. **Provider daily bars are never stored.** Our 1d candles are built from our own verified 1h bars, with the trading day ending at 17:00 America/New_York for USD/ILS and XAU/USD. 4h bars are UTC-aligned and also derived. |
| `exchange` is `"Forex"` for XAU/USD | Informational only |
| Errors come as JSON `{"status":"error","code":...}` | 429 → rate limited. Other codes → rejected. The API key is sent in the `Authorization: apikey` header, never in the URL. |

**Credit budget.** The polling schedule must fit `GMI_TWELVEDATA_CREDITS_PER_MINUTE` and `..._PER_DAY` × headroom (0.9), or
the application refuses to start when ingestion is enabled. Example: the default schedule (quotes every 60 s, 1m candles every
300 s, 1h candles hourly, 2 symbols) needs a peak of 6 credits/min and 3,504/day. That **does not fit Basic** (800/day) and
fits Grow $29 (55/min, no daily cap). Polling is skipped while the session calendar is closed.

**USD/ILS cross-check.** Each business day, the verified Twelve Data USD/ILS price nearest the BoI publication time (±15 min;
`published_at` from the BoI API, otherwise 15:30 Asia/Jerusalem, an **assumption to verify**) is compared with the BoI
representative rate. A difference above **0.5 %** (`GMI_BOI_CROSSCHECK_THRESHOLD_PCT`) logs a `reference_divergence` event.

## Rules

1. No provider credential is ever sent to the frontend.
2. Every stored observation has `provider_id`, `observed_at` and `received_at`.
3. If a provider is missing or unlicensed, its data is shown as **unavailable**. Nothing is substituted or estimated.
4. **BTCUSD comes only from USD-quoted sources (Coinbase BTC-USD, CoinGecko USD).** Binance BTCUSDT is stored under its own
   instrument `BTCUSDT` (quote currency USDT) and is never relabelled, merged or substituted into BTCUSD.
5. CoinGecko attribution and the TradingView attribution are shown in the UI wherever their data or charts appear.
6. Because the individual licences forbid third-party display, the deployment is **single-user and login-only**.

## Verification log

| Date | Item | Method | Result |
|---|---|---|---|
| 2026-10-31 | Twelve Data, Coinbase, Binance, CoinGecko terms and limits | Web-search snippets (provider sites unreachable from the build sandbox) | See plan §0.3, gates G1–G8. Not yet verified against the full provider pages. |
| 2026-10-31 | Twelve Data Grow pricing | Owner | $29 / $49 / $79 by credits/min. $29 = 55 credits/min. |
| 2026-10-31 | Twelve Data `/quote` USD/ILS and XAU/USD | Owner, free Basic key, ~10:27 UTC; responses saved as recorded fixtures | Coverage confirmed. No bid/ask. Strings for numbers. `is_market_open` unreliable. Daily bar starts 16:00 New York. |
| 2026-10-31 | Coinbase, BoI reachability from build sandbox | `curl` | Blocked by the sandbox egress policy (proxy 403). Not a provider restriction. To be tested on the VPS. |
