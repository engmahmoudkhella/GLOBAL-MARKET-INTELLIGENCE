"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { csrfToken } from "@/lib/csrf";

export function LogoutButton() {
  const t = useTranslations("shell");
  const router = useRouter();
  async function logout() {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken() },
      credentials: "same-origin",
    }).catch(() => undefined);
    router.replace("/login");
    router.refresh();
  }
  return (
    <button
      type="button"
      onClick={logout}
      className="rounded px-2 py-0.5 text-sm text-slate-700 hover:bg-slate-100"
    >
      {t("logout")}
    </button>
  );
}
