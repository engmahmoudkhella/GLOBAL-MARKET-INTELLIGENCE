# GMI – Data Sources, Coverage, Licensing and Limitations

**Status:** Providers selected (2026-10-31, plan §0). No provider is integrated yet (Phase 2). Terms, rate limits and pricing **must be re-verified
against each provider's current documentation and terms of service before integration**. They change often and are
listed here only as planning assumptions.

| Provider | Instruments / data | Access | Licensing notes | Known limitations | Status |
|---|---|---|---|---|---|
| Bank of Israel | USD/ILS representative rate, BoI policy rate, Israeli series | Public website / series API | Public data. Attribution required. | Once per business day. **Not an executable price.** No intraday data. | Planned (Phase 2) |
| Israel CBS | Israeli CPI, GDP, unemployment, trade | Public | Public data | Release formats vary | Planned (Phase 4) |
| **Twelve Data – Grow** (individual plan) | **USD/ILS and XAU/USD** quotes and OHLCV | Paid individual plan, API key | Basic/Grow: **personal, non-commercial use only. No display or redistribution to third parties.** This fits the single-user deployment. | Per-minute API credit limit (no daily cap on Grow). Quotes are indicative, not a bank's executable rate. **XAU/USD and USD/ILS coverage on Grow are unconfirmed (gates G1/G2).** | **Selected**. Verify G1–G3 before Phase 2. |
| CME/COMEX via vendor | Gold futures | Paid | Exchange fees | Optional | Optional |
| **Coinbase Exchange** | **BTC-USD primary**: ticker, candles, order book, trades, WebSocket feed | Public endpoints, no key (`api.exchange.coinbase.com`) | Coinbase **Market Data Terms of Use** apply. Personal-use wording **not yet verified (G5)**. | About 10 req/s per IP (burst 15). Servers reported in AWS us-east-1. Reachability from EU VPS to test (G6). Candles endpoint returns at most 300 buckets per request. | **Selected** (Phase 2) |
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
