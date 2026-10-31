"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { useRouter } from "@/i18n/navigation";

export function LoginForm() {
  const t = useTranslations("login");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
        credentials: "same-origin",
      });
      if (res.ok) {
        router.replace("/overview");
        router.refresh();
        return;
      }
      setError(res.status === 401 ? t("invalid") : res.status === 429 ? t("rateLimited") : t("error"));
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3" noValidate>
      <label className="block text-sm">
        <span className="mb-1 block">{t("email")}</span>
        <input
          name="email"
          type="email"
          autoComplete="username"
          required
          dir="ltr"
          className="w-full rounded border border-slate-300 px-2 py-1.5"
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block">{t("password")}</span>
        <input
          name="password"
          type="password"
          autoComplete="current-password"
          required
          dir="ltr"
          className="w-full rounded border border-slate-300 px-2 py-1.5"
        />
      </label>
      {error && (
        <p role="alert" data-testid="login-error" className="text-sm text-red-700">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="w-full rounded bg-slate-900 py-1.5 text-sm font-medium text-white disabled:opacity-60"
      >
        {busy ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
