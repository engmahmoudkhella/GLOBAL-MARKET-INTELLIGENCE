"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";

export function LanguageSwitch() {
  const t = useTranslations("shell");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const other = locale === "ar" ? "en" : "ar";
  return (
    <button
      type="button"
      data-testid="language-switch"
      lang={other}
      onClick={() => router.replace(pathname, { locale: other })}
      className="rounded border border-slate-300 px-2 py-0.5 text-sm hover:bg-slate-100"
    >
      {t("language")}
    </button>
  );
}
