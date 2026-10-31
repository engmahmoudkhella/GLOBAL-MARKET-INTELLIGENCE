/** Navigation sections (SRS §15.1 plus "Forecast Track Record", plan §0.4). */
export const SECTIONS = [
  { slug: "overview", phase: 8 },
  { slug: "market-monitor", phase: 2 },
  { slug: "usdils", phase: 4 },
  { slug: "gold", phase: 4 },
  { slug: "bitcoin", phase: 4 },
  { slug: "forecast-center", phase: 5 },
  { slug: "forecast-track-record", phase: 5 },
  { slug: "cross-asset", phase: 6 },
  { slug: "news", phase: 4 },
  { slug: "calendar", phase: 4 },
  { slug: "technical", phase: 4 },
  { slug: "signals", phase: 5 },
  { slug: "paper-trading", phase: 7 },
  { slug: "portfolio", phase: 7 },
  { slug: "importer-advisor", phase: 3 },
  { slug: "backtesting", phase: 7 },
  { slug: "model-performance", phase: 5 },
  { slug: "alerts", phase: 8 },
  { slug: "reports", phase: 8 },
  { slug: "data-sources", phase: 2 },
  { slug: "settings", phase: 8 },
] as const;

export type SectionSlug = (typeof SECTIONS)[number]["slug"];

export function findSection(slug: string) {
  return SECTIONS.find((s) => s.slug === slug);
}
