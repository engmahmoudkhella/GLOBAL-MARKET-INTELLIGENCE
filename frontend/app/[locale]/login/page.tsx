import { getTranslations, setRequestLocale } from "next-intl/server";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { LoginForm } from "@/components/LoginForm";
import { redirect } from "@/i18n/navigation";
import { getCurrentUser } from "@/lib/api";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  if (await getCurrentUser().catch(() => null)) {
    redirect({ href: "/overview", locale });
  }
  const t = await getTranslations();
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold">{t("app.name")}</h1>
          <LanguageSwitch />
        </div>
        <h2 className="mb-4 text-base font-medium">{t("login.title")}</h2>
        <LoginForm />
        <p className="mt-4 text-xs text-slate-500">{t("login.noSignup")}</p>
        <p className="mt-2 text-xs font-medium text-amber-700">{t("app.paperOnly")}</p>
      </div>
    </main>
  );
}
