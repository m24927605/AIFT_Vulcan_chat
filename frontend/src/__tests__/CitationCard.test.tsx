import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CitationCard } from "@/components/CitationCard";

describe("CitationCard", () => {
  it("extracts and displays domain from URL", () => {
    render(
      <CitationCard
        citation={{
          index: 1,
          title: "Test Article",
          url: "https://www.example.com/page",
          snippet: "...",
        }}
      />
    );

    expect(screen.getByText("example.com")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText("Test Article")).toBeDefined();
  });

  it("sanitizes javascript: URLs to #", () => {
    render(<CitationCard citation={{ index: 3, title: "Malicious", url: "javascript:alert('xss')", snippet: "..." }} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("#");
  });

  it("allows https: URLs", () => {
    render(<CitationCard citation={{ index: 4, title: "Safe", url: "https://example.com/safe", snippet: "..." }} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("https://example.com/safe");
  });

  it("sanitizes data: URLs to #", () => {
    render(<CitationCard citation={{ index: 5, title: "Data", url: "data:text/html,<script>alert(1)</script>", snippet: "..." }} />);
    expect(screen.getByRole("link").getAttribute("href")).toBe("#");
  });

  it("renders data source citation without link", () => {
    render(
      <CitationCard
        citation={{
          index: 1,
          title: "Fugle: 2330 fugle_quote",
          url: "",
          snippet: "price data",
        }}
      />
    );

    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText("Data Source")).toBeDefined();
    expect(screen.getByText("Fugle: 2330 fugle_quote")).toBeDefined();
    // Should NOT be an <a> tag
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("falls back to raw URL on invalid URL", () => {
    render(
      <CitationCard
        citation={{
          index: 2,
          title: "Broken Link",
          url: "not-a-valid-url",
          snippet: "...",
        }}
      />
    );

    expect(screen.getByText("not-a-valid-url")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
  });
});
