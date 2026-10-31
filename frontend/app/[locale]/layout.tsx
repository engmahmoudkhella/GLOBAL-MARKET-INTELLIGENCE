import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { directionOf, routing } from "@/i18n/routing";
import "../globals.css";

export const metadata: Metadata = {
  title: "GMI – Global Market Intelligence",
  robots: { index: false, follow: false },
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  return (
    <html lang={locale} dir={directionOf(locale)}>
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  );
}
