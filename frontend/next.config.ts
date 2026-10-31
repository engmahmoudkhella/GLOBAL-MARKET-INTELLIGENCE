import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Server-side only. The browser always talks to the same origin (/api/...), which nginx
// (production) or the rewrite below (development) forwards to FastAPI. No API keys ever
// reach the frontend.
const apiInternal = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiInternal}/api/:path*` },
      { source: "/health/:path*", destination: `${apiInternal}/health/:path*` },
    ];
  },
};

export default withNextIntl(nextConfig);
