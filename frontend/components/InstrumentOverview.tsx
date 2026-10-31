import { getFormatter, getTranslations } from "next-intl/server";
import { apiGet, type Instrument, type QuoteStatus } from "@/lib/api";
import { roundDecimalString } from "@/lib/decimal";

const STATUS_STYLE: Record<QuoteStatus["data_status"], string> = {
  fresh: "bg-emerald-100 text-emerald-900",
  stale: "bg-red-100 text-red-900",
  market_closed: "bg-slate-200 text-slate-800",
  no_data: "bg-slate-100 text-slate-600",
};

/** Shows instrument *configuration* only. No prices exist until phase 2. */
export async function InstrumentOverview() {
  const t = await getTranslations("overview");
  const format = await getFormatter();
  const { items } = await apiGet<{ items: Instrument[]; total: number }>("/api/v1/instruments");
  const quotes = new Map<string, QuoteStatus>();
  await Promise.all(
    items
      .filter((i) => i.role === "primary")
      .map(async (i) => {
        quotes.set(i.symbol, await apiGet<QuoteStatus>(`/api/v1/markets/${i.symbol}/quote`));
      }),
  );
  return (
    <div className="space-y-4">
      <p className="rounded border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
        {t("noMarketData")}
      </p>
      <h2 className="text-base font-medium">{t("instruments")}</h2>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((i) => (
          <article
            key={i.symbol}
            data-testid={`instrument-${i.symbol}`}
            className="rounded-lg border border-slate-200 bg-white p-4"
          >
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="ltr-num font-semibold">{i.display_name}</h3>
              <span className="text-xs text-slate-500">
                {i.role === "primary" ? t("primary") : t("secondary")}
              </span>
            </div>
            {quotes.has(i.symbol) && (
              <QuoteBlock
                q={quotes.get(i.symbol)!}
                precision={i.configuration.price_precision}
                t={t}
                formatTime={(iso) =>
                  format.dateTime(new Date(iso), {
                    year: "numeric",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    timeZoneName: "short",
                  })
                }
              />
            )}
            <dl className="mt-3 space-y-2 text-sm">
              <div>
                <dt className="text-slate-500">{t("horizons")}</dt>
                <dd className="ltr-num">
                  {i.configuration.forecasting_enabled
                    ? i.configuration.forecast_horizons.join(" · ")
                    : t("noForecasting")}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">{t("sources")}</dt>
                <dd>
                  <ul className="space-y-0.5">
                    {i.providers.map((p) => (
                      <li key={p.provider}>
                        {p.provider_display_name}{" "}
                        <span className="text-xs text-slate-500">
                          ({t(`purpose.${p.purpose}`)}, {t("providerStatus", { status: p.provider_status })})
                        </span>
                      </li>
                    ))}
                  </ul>
                </dd>
              </div>
            </dl>
            {i.providers.some((p) => p.provider === "coingecko") && (
              <p className="mt-3 text-xs text-slate-500" lang="en" dir="ltr">
                <a
                  href="https://www.coingecko.com/en/api"
                  target="_blank"
                  rel="noopener noreferrer"
                  data-testid={`attribution-coingecko-${i.symbol}`}
                  className="underline"
                >
                  Powered by CoinGecko API
                </a>
              </p>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}

function QuoteBlock({
  q,
  precision,
  t,
  formatTime,
}: {
  q: QuoteStatus;
  precision: number;
  t: Awaited<ReturnType<typeof getTranslations<"overview">>>;
  formatTime: (iso: string) => string;
}) {
  const price = q.price_type === "mid" ? q.mid : q.last_price;
  return (
    <div className="mt-3 space-y-1" data-testid={`quote-${q.symbol}`}>
      <span
        data-testid={`status-${q.symbol}`}
        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[q.data_status]}`}
      >
        {t(`status.${q.data_status}`)}
      </span>
      {price && q.observed_at && q.provider && (
        <>
          <p className="ltr-num text-lg font-semibold">
            {roundDecimalString(price, precision)} <span className="text-xs font-normal text-slate-500">({t(`priceType.${q.price_type}`)})</span>
          </p>
          <p className="text-xs text-slate-500">
            {t("observedAt", { time: formatTime(q.observed_at), provider: q.provider })}
          </p>
        </>
      )}
      {q.latest_excluded && (
        <div
          data-testid={`excluded-${q.symbol}`}
          className="rounded border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900"
        >
          <p className="font-medium">
            {t("excluded.title")}:{" "}
            {q.latest_excluded.reasons.includes("out_of_session")
              ? t("excluded.reason.out_of_session")
              : t("excluded.reason.other")}
          </p>
          {q.latest_excluded.price && q.latest_excluded.price_type && (
            <p className="ltr-num">
              {t("excluded.detail", {
                price: roundDecimalString(q.latest_excluded.price, precision),
                type: t(`priceType.${q.latest_excluded.price_type}`),
                time: formatTime(q.latest_excluded.observed_at),
              })}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
