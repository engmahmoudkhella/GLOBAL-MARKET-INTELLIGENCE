import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { InstrumentOverview } from "@/components/InstrumentOverview";
import { findSection } from "@/lib/sections";

export default async function SectionPage({
  params,
}: {
  params: Promise<{ locale: string; section: string }>;
}) {
  const { locale, section } = await params;
  setRequestLocale(locale);
  const meta = findSection(section);
  if (!meta) notFound();
  const t = await getTranslations();
  return (
    <section>
      <h1 className="mb-4 text-xl font-semibold" data-testid="section-title">
        {t(`sections.${meta.slug}`)}
      </h1>
      {meta.slug === "overview" ? (
        <InstrumentOverview />
      ) : (
        <div className="rounded-md border border-dashed border-slate-300 bg-white p-6">
          <p className="font-medium">{t("notImplemented.title")}</p>
          <p className="mt-1 text-sm text-slate-600">
            {t("notImplemented.body", { phase: meta.phase })}
          </p>
        </div>
      )}
    </section>
  );
}
