import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Everything except API/health (served by FastAPI), Next internals and static files.
  matcher: ["/((?!api|health|_next|_vercel|.*\\..*).*)"],
};
