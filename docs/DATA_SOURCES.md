# GMI – Data Sources, Coverage, Licensing and Limitations

**Status:** Candidate list. No provider is integrated yet. Terms, rate limits and pricing **must be re-verified
against each provider's current documentation and terms of service before integration**. They change often and are
listed here only as planning assumptions.

| Provider | Instruments / data | Access | Licensing notes | Known limitations | Status |
|---|---|---|---|---|---|
| Bank of Israel | USD/ILS representative rate, BoI policy rate, Israeli series | Public website / series API | Public data. Attribution required. | Once per business day. **Not an executable price.** No intraday data. | Planned (Phase 2) |
| Israel CBS | Israeli CPI, GDP, unemployment, trade | Public | Public data | Release formats vary | Planned (Phase 3) |
| Licensed FX vendor (TBD – D1) | USD/ILS intraday bid/ask, OHLCV | Paid API | Display/redistribution licence needed for multi-user UI | ILS liquidity varies by session | **Decision pending** |
| Licensed metals vendor (TBD – D1) | XAU/USD spot bid/ask, OHLCV | Paid API | Same as above. LBMA benchmark prices are IBA-licensed. | — | **Decision pending** |
| CME/COMEX via vendor | Gold futures | Paid | Exchange fees | Optional | Optional |
| Binance | BTCUSDT spot ticker, klines, order book, WebSocket; futures funding rate and open interest | Public endpoints, no key | Binance terms of use apply. Check redistribution terms. | **Geo-restricted** (e.g. US). Weight-based rate limits. Quote currency is USDT, not USD. | Planned (Phase 2) |
| CoinGecko | BTC/USD reference price, market cap, history | Free Demo key / paid | Attribution required. Commercial use needs a paid plan. | Low free-tier rate limits | Planned (Phase 2) |
| FRED / ALFRED (St. Louis Fed) | Fed funds, Treasury yields, real yields (TIPS), CPI, PCE, Broad Dollar Index | Free API key | Public. Some series carry third-party copyright notices. | Data revisions. Use ALFRED vintages for point-in-time. | Planned (Phase 3) |
| BLS, BEA, US Treasury | CPI, NFP, unemployment, GDP, PCE, yield curve | Free (keys for BLS/BEA) | Public | — | Planned (Phase 3) |
| ICE DXY | US Dollar Index | Licensed | Proprietary | — | Not planned unless licensed (D4) |
| CFTC | Commitments of Traders (gold) | Free | Public | Weekly, lagged | Planned (Phase 3) |
| World Gold Council | ETF flows, central bank purchases | Website | Terms restrict automated reuse | — | Manual / licence required |
| Coinglass / Glassnode / CryptoQuant | Liquidations, on-chain, exchange netflows, ETF flows | Paid | Commercial licences | Optional modules | Optional |
| GDELT, official RSS (Fed, BoI, Treasury, SEC) | News EN/AR | Free | Store title, summary and link only | Coverage and quality vary | Planned (Phase 3) |
| Telegram Bot API | Alert delivery | Free | — | Per-chat rate limits | Planned (Phase 7) |

## Rules

1. No provider credential is ever sent to the frontend.
2. Every stored observation has `provider_id`, `observed_at` and `received_at`.
3. If a provider is missing or unlicensed, its data is shown as **unavailable**. Nothing is substituted or estimated.
4. When BTCUSDT is used as a proxy for BTC/USD, the UI and docs state it.
