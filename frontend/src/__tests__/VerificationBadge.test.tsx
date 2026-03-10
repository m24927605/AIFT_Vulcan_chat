import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VerificationBadge } from "@/components/VerificationBadge";

describe("VerificationBadge", () => {
  it("renders nothing when verification is null", () => {
    const { container } = render(<VerificationBadge verification={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders compact badge when is_consistent is true", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: true,
          confidence: 0.95,
          issues: [],
          suggestion: "",
        }}
      />
    );

    expect(screen.getByText(/95%/)).toBeDefined();
    // Should NOT show issues section
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("renders expanded panel when is_consistent is false", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: false,
          confidence: 0.6,
          issues: ["Source A contradicts source B", "Date mismatch"],
          suggestion: "Cross-check with official records",
        }}
      />
    );

    expect(screen.getByText(/60%/)).toBeDefined();
    expect(screen.getByText("Source A contradicts source B")).toBeDefined();
    expect(screen.getByText("Date mismatch")).toBeDefined();
    expect(screen.getByText("Cross-check with official records")).toBeDefined();
  });

  it("does not render issues list when is_consistent is true even if issues exist", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: true,
          confidence: 0.88,
          issues: [],
          suggestion: "",
        }}
      />
    );

    expect(screen.queryByRole("list")).toBeNull();
  });

  it("does not render suggestion text when suggestion is empty", () => {
    render(
      <VerificationBadge
        verification={{
          is_consistent: false,
          confidence: 0.5,
          issues: ["Problem found"],
          suggestion: "",
        }}
      />
    );

    expect(screen.getByText("Problem found")).toBeDefined();
    // Suggestion label should not appear
    expect(screen.queryByText(/Suggestion/i)).toBeNull();
  });
});
