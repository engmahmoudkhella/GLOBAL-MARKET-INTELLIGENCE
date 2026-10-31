/** Reads the CSRF cookie set at login so state-changing requests can echo it. */
export function csrfToken(): string {
  const m = document.cookie.match(/(?:^|; )gmi_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}
