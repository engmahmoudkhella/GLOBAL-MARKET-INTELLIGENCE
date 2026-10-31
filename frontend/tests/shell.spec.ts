import { expect, test, type Page } from "@playwright/test";

const EMAIL = process.env.E2E_EMAIL ?? "";
const PASSWORD = process.env.E2E_PASSWORD ?? "";

async function signIn(page: Page, locale: "ar" | "en") {
  await page.goto(`/${locale}/login`);
  await page.locator('input[name="email"]').fill(EMAIL);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(`**/${locale}/overview`);
}

test.beforeAll(() => {
  if (!EMAIL || !PASSWORD) throw new Error("E2E_EMAIL and E2E_PASSWORD must be set");
});

for (const [locale, dir, title] of [
  ["ar", "rtl", "تسجيل الدخول"],
  ["en", "ltr", "Sign in"],
] as const) {
  test(`login page renders ${locale} with dir=${dir}`, async ({ page }) => {
    await page.goto(`/${locale}/login`);
    await expect(page.locator("html")).toHaveAttribute("dir", dir);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  });
}

test.describe("default locale", () => {
  // A browser language that matches neither locale falls back to Arabic.
  test.use({ locale: "fr-FR" });
  test("root redirects to Arabic when no supported language is preferred", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/ar(\/|$)/);
  });
});

test.describe("browser language detection", () => {
  test.use({ locale: "en-US" });
  test("root redirects to English for an English browser", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/en(\/|$)/);
  });
});

test("protected pages redirect to login when signed out", async ({ page }) => {
  await page.goto("/en/overview");
  await expect(page).toHaveURL(/\/en\/login$/);
});

test("wrong password shows a generic error", async ({ page }) => {
  await page.goto("/en/login");
  await page.locator('input[name="email"]').fill(EMAIL);
  await page.locator('input[name="password"]').fill("definitely-not-the-password");
  await page.locator('button[type="submit"]').click();
  await expect(page.getByTestId("login-error")).toHaveText("Invalid email or password.");
});

test("signed-in shell: paper-only banner, 21 sections, instruments without prices", async ({
  page,
}) => {
  await signIn(page, "en");
  await expect(page.getByTestId("paper-only-banner")).toContainText("Paper trading only");
  const nav = page.getByRole("navigation");
  await expect(nav.getByRole("link")).toHaveCount(21);
  await expect(nav.getByRole("link", { name: "Forecast Track Record" })).toBeVisible();
  for (const sym of ["USDILS", "XAUUSD", "BTCUSD", "BTCUSDT"]) {
    await expect(page.getByTestId(`instrument-${sym}`)).toBeVisible();
  }
  await expect(page.getByTestId("instrument-USDILS")).toContainText("30d");
  await expect(page.getByTestId("instrument-BTCUSD")).toContainText("Coinbase");
  // Freshness is always visible; with no verified data it says so and shows no price.
  for (const sym of ["USDILS", "XAUUSD", "BTCUSD"]) {
    await expect(page.getByTestId(`status-${sym}`)).toHaveText("No data yet");
  }
  // The e2e seed ingested the owner's recorded Saturday USD/ILS quote: it must be shown as
  // excluded (market closed), never as the current price.
  const excluded = page.getByTestId("excluded-USDILS");
  await expect(excluded).toContainText("Excluded quote (not used): Market closed / weekend");
  await expect(excluded).toContainText("3.1415 (last)");
  await expect(page.getByTestId("excluded-XAUUSD")).toHaveCount(0);
  // CoinGecko attribution wherever CoinGecko is a configured source (Demo plan terms)
  await expect(page.getByTestId("attribution-coingecko-BTCUSD")).toHaveText(
    "Powered by CoinGecko API",
  );

  await nav.getByRole("link", { name: "Forecast Track Record" }).click();
  await expect(page.getByTestId("section-title")).toHaveText("Forecast Track Record");
  await expect(page.getByText("Not implemented yet")).toBeVisible();
});

test("language switch keeps the page and flips direction", async ({ page }) => {
  await signIn(page, "ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("navigation").getByRole("link", { name: "سجل دقة التوقعات" }).click();
  await expect(page).toHaveURL(/\/ar\/forecast-track-record$/);
  await page.getByTestId("language-switch").click();
  await expect(page).toHaveURL(/\/en\/forecast-track-record$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
});

test("logout ends the session", async ({ page }) => {
  await signIn(page, "en");
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL("**/en/login");
  await page.goto("/en/overview");
  await expect(page).toHaveURL(/\/en\/login$/);
});
