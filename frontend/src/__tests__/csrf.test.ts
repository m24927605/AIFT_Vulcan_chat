import { describe, it, expect } from "vitest";
import { getCsrfToken } from "@/lib/csrf";

describe("getCsrfToken", () => {
  it("returns empty string when no csrf_token cookie", () => {
    Object.defineProperty(document, "cookie", { value: "", writable: true });
    expect(getCsrfToken()).toBe("");
  });

  it("extracts csrf_token from document.cookie", () => {
    Object.defineProperty(document, "cookie", {
      value: "vulcan_session=abc; csrf_token=xyz123; other=val",
      writable: true,
    });
    expect(getCsrfToken()).toBe("xyz123");
  });
});
