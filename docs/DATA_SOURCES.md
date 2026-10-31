# GMI – Data Sources, Coverage, Licensing and Limitations

**Status (2026-10-31, after the owner's browser recordings):** Adapters are implemented for Bank of Israel, Twelve Data,
Coinbase, CoinGecko and Binance. **Verified against recorded live responses:** BoI PublicApi JSON, BoI SDMX
(structure only, browser copy), Twelve Data `/quote`, `/time_series` and `/api_usage`, Coinbase ticker and candles.
**Still documentation-based (unverified):** Coinbase order book, product status and time; CoinGecko; Binance. Terms, rate limits and pricing **must be re-verified
against each provider's current documentation and terms of service before integration**. They change often and are
listed here only as planning assumptions.

| Provider | Instruments / data | Access | Licensing notes | Known limitations | Status |
|---|---|---|---|---|---|
| Bank of Israel | USD/ILS representative rate, BoI policy rate, Israeli series | Public website / series API | Public data. Attribution required. | Published **Monday–Friday** around midday Israel time (observed `lastUpdate` 12:21 IST). **Not an executable price.** No intraday data. Stored in `official_reference_rates`, never as quotes. | **Adapter implemented** (`app/providers/boi.py`). Latest via `www.boi.org.il/PublicApi/GetExchangeRates` (recorded). History via `edge.boi.org.il` SDMX-ML 2.1 XML (structure verified from a browser copy). See BoI notes below. |
| Israel CBS | Israeli CPI, GDP, unemployment, trade | Public | Public data | Release formats vary | Planned (Phase 4) |
| **Twelve Data – Grow** (individual plan) | **USD/ILS and XAU/USD** quotes and OHLCV | Paid individual plan, API key | Basic/Grow: **personal, non-commercial use only. No display or redistribution to third parties.** This fits the single-user deployment. | Per-minute API credit limit (no daily cap on Grow). Quotes are indicative, not a bank's executable rate. See **Twelve Data contract notes** below. | **Adapter implemented** (`app/providers/twelvedata.py`). Coverage of USD/ILS and XAU/USD **confirmed** (G1/G2, owner test 2026-10-31). **Free Basic key for development only** (8 credits/min, 800/day, non-display). **Switch to Grow $29 (55 credits/min) before live ingestion on the VPS.** |
| CME/COMEX via vendor | Gold futures | Paid | Exchange fees | Optional | Optional |
| **Coinbase Exchange** | **BTC-USD primary**: ticker, candles, order book, trades, WebSocket feed | Public endpoints, no key (`api.exchange.coinbase.com`) | Coinbase **Market Data Terms of Use** apply. Personal-use wording **not yet verified (G5)**. | About 10 req/s per IP (burst 15). Servers reported in AWS us-east-1. Reachability from EU VPS to test (G6). Candles endpoint returns at most 300 buckets per request. Granularities 1m/5m/15m/1h/6h/1d only (no 4h; our 4h/1d are derived from 1h). | **Adapter implemented.** Ticker and candles **verified against recordings** (see Coinbase notes). Book, product and time are doc-based. |
| Binance | **BTCUSDT secondary series** (separate from BTCUSD); futures funding rate and open interest | Public endpoints, no key; `data-api.binance.vision` spot-only mirror | Binance terms of use apply | **EU services limited since July 2026 (G7)**. HTTP 451 in blocked regions (treated as rejected, not retried). Quote currency is **USDT and is never relabelled as USD**. bookTicker has **no timestamp**, so observed_at = reception time (flagged). | **Adapter implemented** (`app/providers/binance.py`, host `data-api.binance.vision`), doc-based. Feeds only `BTCUSDT`. `GMI_BINANCE_ENABLED`. |
| **CoinGecko – Demo** | BTC/USD independent reference price, market cap, history | Free Demo API key | **Attribution required**: a "Powered by CoinGecko API" link in the UI | 30 calls/min, 10,000 calls/month. Config validation enforces the monthly budget (default poll every 300 s = 8,928 calls/month max). | **Adapter implemented** (`app/providers/coingecko.py`), doc-based. Reference only. Cross-checked against Coinbase mid (event above 0.5 %). Attribution link shown in the UI. |
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
`published_at` from the BoI API, otherwise **12:30 Asia/Jerusalem**, a configurable **assumption**) is compared with the BoI
representative rate. A difference above **0.5 %** (`GMI_BOI_CROSSCHECK_THRESHOLD_PCT`) logs a `reference_divergence` event.

## Bank of Israel notes (owner recordings 2026-10-31)

| Observation | Handling |
|---|---|
| `currentExchangeRate`, `currentChange` are **JSON numbers** | Parsed with `parse_float=Decimal` from the raw text, never via float. Strings are rejected as a contract change. |
| `unit` (JPY = 100, LBP = 10) | Rate stored **per 1 unit** (`rate / unit`). The published rate and unit are kept raw in `attributes_json`. |
| `currentChange` is a **percentage** | Stored raw as `current_change_pct`. Not interpreted. |
| `lastUpdate` 2026-10-30T10:21:03Z = **12:21 Israel time** | Used as `published_at`. **Every distinct `lastUpdate` is stored** (`boi_publication_observations`). For history without timestamps, `GMI_BOI_PUBLICATION_FALLBACK_TIME` (default **12:30 Asia/Jerusalem, assumption**) is used, and the cross-check window follows it. After 20 business days, the median and range are reported (`boi-publication-stats`) and the owner decides the fallback. It is **never changed automatically**. |
| Observations Mon–Fri only (Fri 23 and Fri 30 Oct present, Sat and Sun absent) | Publication calendar = Monday–Friday minus `boi` holidays. |
| **Tue 27 Oct 2026 missing**: **Knesset election day**, a statutory day off (Basic Law: The Knesset, s.10; source https://www.shibolet.com/?p=27864) | Seeded in `special_closures` for the `boi` calendar. Not expected, so no new gap is raised. An earlier `missing_reference` event for that day is **kept and marked "explained: holiday"**. Never filled. |
| SDMX `RELEASE_STATUS="YP"`, series attributes (`DATA_SOURCE`, `TIME_COLLECT`, …) | Stored raw in `attributes_json`. Not interpreted. |
| SDMX schemaLocation references `edge.boi.gov.il` | The reachability script checks `www.boi.org.il`, `edge.boi.org.il` and `edge.boi.gov.il`. |
| The XML sample is a **browser copy, not byte-exact** | Used for structure only. Re-record raw from the VPS (`check_provider_contracts.py --save`). |

## Coinbase notes (owner recordings 2026-10-31)

- Ticker `bid`/`ask`/`price` are **strings**, so BTC gets a true mid. `time` arrives with **9 or 6** fractional digits (both handled).
  Unknown extra fields (e.g. `rfq_volume`) are ignored and **logged once**. Required fields are strict.
- Candles: rows are **[time, LOW, HIGH, OPEN, CLOSE, volume]**, JSON numbers, newest first. Columns are mapped by position, and
  `low ≤ open, close ≤ high` is asserted (a violation means the column order changed, so the response is rejected).
- The current hour is incomplete. **Any candle ending after the response time is dropped**, for every provider.
- The recorded hourly response (no start/end parameters) had **350 rows, 1793440800 back to 1792184400: 350 consecutive hourly
  buckets with no gaps** (owner check of the full file). The documentation states a 300-bucket maximum; the adapter still requests at
  most 300 buckets per call, which is safe either way.

## Twelve Data notes (owner recordings 2026-10-31, continued)

- `/time_series` **without `timezone=UTC` is not UTC**: the latest bar was labelled 21:00 at about 10:58 UTC, and `meta` has no timezone field.
  The adapter always sends `timezone=UTC` and **rejects a response whose bars start in the future**.
- `/api_usage` reports `plan_limit` (8), `plan_daily_limit` (800) and `plan_category` ("basic"). **Celery Beat verifies the real plan
  at startup** and refuses to start if the configured limits exceed it, or the schedule does not fit it.
- On 30 Oct the BoI rate was 3.118, while Twelve Data's close and last price were about 3.141–3.142 (**about 0.77 %**). This is
  **expected**: BoI fixed at 10:21 UTC on Friday, while Twelve Data's close is the New York close. The cross-check compares only
  prices within ±15 min of the BoI publication, with a 0.5 % threshold (both kept, owner decision).

## Holiday calendars

Stored in `market_holidays`. **Every seeded row is flagged `is_assumption`** until confirmed by observed data:
- `fx`, `xau`: 25 Dec 2026, 1 Jan 2027 and 25 Dec 2028 (confirmed acceptable by the owner). The session day ending 17:00
  New York on that date is closed.
- `xau` **reduced liquidity / possible closure (not a closure)**: Good Friday and Easter Monday (London bullion holidays)
  2027 and 2028 (`kind = reduced_liquidity`). The market stays open in the calendar, and any gap on those days is annotated
  `reduced_liquidity_day`. **Assumption, to be verified against real Twelve Data data on Good Friday, 26 Mar 2027**
  (`app.cli verify-holiday --day 2027-03-26`).
- `boi`: Israeli full rest days 2026–2028 falling on weekdays, computed with `pyluach` plus the statutory Yom HaAtzmaut rules
  (accepted by the owner).
- **Special closures** (`special_closures`): manual, non-algorithmic closures (election days, one-off government holidays), each
  with a date, calendar key, reason and **source URL**. Seed: 2026-10-27 (`boi`), Knesset election day.
- **Authority:** where the Bank of Israel publishes its own non-publication calendar, **that list is authoritative** and should
  replace the computed dates once it can be fetched from the VPS. Until then the computed list plus special closures applies.

Holidays make the market closed for out-of-session checks, gap detection, derived candles and the BoI publication calendar.

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
| 2026-10-31 | BoI JSON + SDMX, Coinbase ticker + candles, Twelve Data time_series + api_usage | Owner, browser in Gaza, ~10:56–10:59 UTC; saved as fixtures | Findings A–I (see the notes above) |
| 2026-10-31 | Coinbase, BoI reachability from build sandbox | `curl` | Blocked by the sandbox egress policy (proxy 403). Not a provider restriction. To be tested on the VPS. |
