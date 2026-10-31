import { getTranslations, setRequestLocale } from "next-intl/server";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { LogoutButton } from "@/components/LogoutButton";
import { SideNav } from "@/components/SideNav";
import { redirect } from "@/i18n/navigation";
import { getCurrentUser } from "@/lib/api";

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const user = await getCurrentUser();
  if (!user) {
    redirect({ href: "/login", locale });
    return null;
  }
  const t = await getTranslations();
  return (
    <div className="flex min-h-screen flex-col">
      <div
        role="status"
        data-testid="paper-only-banner"
        className="bg-amber-100 px-4 py-1 text-center text-xs font-medium text-amber-900"
      >
        {t("app.paperOnly")}
      </div>
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
        <span className="font-semibold">{t("app.name")}</span>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-slate-600 sm:inline">
            {t("shell.signedInAs", { name: user.name })}
          </span>
          <LanguageSwitch />
          <LogoutButton />
        </div>
      </header>
      <div className="flex flex-1 flex-col md:flex-row">
        <SideNav />
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
