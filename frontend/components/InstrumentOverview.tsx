import { getTranslations } from "next-intl/server";
import { apiGet, type Instrument } from "@/lib/api";

/** Shows instrument *configuration* only. No prices exist until phase 2. */
export async function InstrumentOverview() {
  const t = await getTranslations("overview");
  const { items } = await apiGet<{ items: Instrument[]; total: number }>("/api/v1/instruments");
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
          </article>
        ))}
      </div>
    </div>
  );
}
