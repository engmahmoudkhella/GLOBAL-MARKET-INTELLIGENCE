import { expect, test } from "@playwright/test";
import { roundDecimalString } from "../../lib/decimal";

// Pure-function tests run with the Playwright runner (no browser needed).
test("rounds decimal strings exactly", () => {
  expect(roundDecimalString("12345.2000000000", 2)).toBe("12345.20");
  expect(roundDecimalString("3.7124999999", 4)).toBe("3.7125");
  expect(roundDecimalString("3.71245", 4)).toBe("3.7125");
  expect(roundDecimalString("3.71244", 4)).toBe("3.7124");
  expect(roundDecimalString("9.995", 2)).toBe("10.00");
  expect(roundDecimalString("99999.999", 2)).toBe("100000.00");
  expect(roundDecimalString("0.004", 2)).toBe("0.00");
  expect(roundDecimalString("-1.005", 2)).toBe("-1.01");
  expect(roundDecimalString("70010", 2)).toBe("70010.00");
  expect(roundDecimalString("1.5", 0)).toBe("2");
  // 0.1 + 0.2 style float artefacts cannot occur: input stays a string
  expect(roundDecimalString("0.30000000000000004", 2)).toBe("0.30");
  expect(() => roundDecimalString("1e5", 2)).toThrow();
});
