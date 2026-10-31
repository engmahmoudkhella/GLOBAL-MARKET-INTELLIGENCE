"use client";

import { useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { SECTIONS } from "@/lib/sections";

export function SideNav() {
  const t = useTranslations();
  const pathname = usePathname();
  return (
    <nav
      aria-label={t("shell.nav")}
      className="border-b border-slate-200 bg-white md:w-60 md:shrink-0 md:border-b-0 md:border-e"
    >
      <ul className="flex gap-1 overflow-x-auto p-2 md:flex-col md:overflow-visible">
        {SECTIONS.map((s) => {
          const href = `/${s.slug}`;
          const active = pathname === href;
          return (
            <li key={s.slug} className="shrink-0">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={`block rounded px-3 py-1.5 text-sm ${
                  active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                {t(`sections.${s.slug}`)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
