import "server-only";
import { cookies } from "next/headers";

const API = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export type User = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
  preferred_language: "ar" | "en";
  timezone: string;
  last_login_at: string | null;
};

export type ProviderMapping = {
  provider: string;
  provider_display_name: string;
  provider_status: string;
  provider_symbol: string;
  purpose: "primary" | "reference" | "secondary";
  priority: number;
  notes: string | null;
};

export type Instrument = {
  symbol: string;
  display_name: string;
  asset_class: string;
  base_currency: string;
  quote_currency: string;
  role: "primary" | "secondary";
  market_status: string;
  enabled: boolean;
  configuration: {
    forecast_horizons: string[];
    forecasting_enabled: boolean;
    price_precision: number;
  };
  providers: ProviderMapping[];
};

export type QuoteStatus = {
  symbol: string;
  provider: string | null;
  data_status: "fresh" | "stale" | "market_closed" | "no_data";
  signals_allowed: boolean;
  mid: string | null;
  last_price: string | null;
  price_type: "mid" | "last" | null;
  observed_at: string | null;
  latest_excluded: {
    price: string | null;
    price_type: "mid" | "last" | null;
    observed_at: string;
    data_quality_status: string;
    reasons: string[];
  } | null;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Server-side fetch to FastAPI, forwarding the user's session cookie. */
export async function apiGet<T>(path: string): Promise<T> {
  const jar = await cookies();
  const res = await fetch(`${API}${path}`, {
    headers: { cookie: jar.toString(), accept: "application/json" },
    cache: "no-store",
  });
  if (!res.ok) throw new ApiError(res.status, `${path} -> ${res.status}`);
  return (await res.json()) as T;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await apiGet<User>("/api/v1/auth/me");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}
