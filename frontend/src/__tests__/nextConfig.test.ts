import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

describe("next config security headers", () => {
  it("exposes headers() function", () => {
    expect(typeof nextConfig.headers).toBe("function");
  });

  it("includes CSP with frame-ancestors none", async () => {
    const rules = await nextConfig.headers?.();
    const global = rules?.find((r) => r.source === "/(.*)")?.headers ?? [];
    const csp = global.find((h) => h.key === "Content-Security-Policy")?.value ?? "";
    expect(csp).toContain("frame-ancestors 'none'");
  });

  it("includes connect-src with self (same-origin proxy)", async () => {
    const rules = await nextConfig.headers?.();
    const global = rules?.find((r) => r.source === "/(.*)")?.headers ?? [];
    const csp = global.find((h) => h.key === "Content-Security-Policy")?.value ?? "";
    expect(csp).toContain("connect-src 'self' ws: wss:");
  });

  it("exposes rewrites() for API proxy", async () => {
    const rewrites = await nextConfig.rewrites?.();
    const rules = Array.isArray(rewrites) ? rewrites : [];
    expect(rules).toContainEqual(
      expect.objectContaining({ source: "/api/:path*" })
    );
  });
});
