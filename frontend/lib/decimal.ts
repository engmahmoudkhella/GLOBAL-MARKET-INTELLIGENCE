/**
 * Round a decimal *string* to `dp` places (half away from zero) without converting to a
 * floating-point number, so displayed prices never pick up binary rounding artefacts.
 */
export function roundDecimalString(value: string, dp: number): string {
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!m) throw new Error(`not a decimal: ${value}`);
  const [, sign, intPart, fracRaw = ""] = m;
  const frac = fracRaw.padEnd(dp + 1, "0");
  let digits = (intPart + frac.slice(0, dp)).split("").map(Number);
  if (Number(frac[dp]) >= 5) {
    let i = digits.length - 1;
    while (i >= 0) {
      if (digits[i] === 9) {
        digits[i] = 0;
        i--;
      } else {
        digits[i]++;
        break;
      }
    }
    if (i < 0) digits = [1, ...digits];
  }
  const s = digits.join("");
  const whole = s.slice(0, s.length - dp).replace(/^0+(?=\d)/, "") || "0";
  const out = dp > 0 ? `${whole}.${s.slice(s.length - dp)}` : whole;
  return /^[0.]+$/.test(out) ? out : sign + out;
}
