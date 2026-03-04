import { test, expect } from "@playwright/test";

test.describe("Chat E2E", () => {
  test("page loads with chat input and sidebar", async ({ page }) => {
    await page.goto("/");

    // Main layout elements are visible
    await expect(page.locator('[data-tour="chat-input"]')).toBeVisible();
    await expect(page.getByPlaceholder(/ask|問/i)).toBeVisible();
  });

  test("can type and submit a message", async ({ page }) => {
    // Mock the SSE endpoint to avoid needing a real backend
    await page.route("**/api/chat", async (route) => {
      const sseBody = [
        'event: planner\ndata: {"needs_search":false,"reasoning":"greeting","search_queries":[],"query_type":"conversational"}\n\n',
        'event: chunk\ndata: {"content":"Hello! How can I help?"}\n\n',
        'event: done\ndata: {}\n\n',
      ].join("");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sseBody,
      });
    });

    // Mock conversations API
    await page.route("**/api/conversations", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, json: [] });
      } else {
        await route.fulfill({
          status: 200,
          json: { id: "test-conv", title: "test" },
        });
      }
    });

    await page.route("**/api/conversations/*/messages", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 1,
            role: "user",
            content: "Hi",
            source: "web",
            search_used: null,
            citations: null,
            created_at: "2026-03-02T00:00:00Z",
          },
          {
            id: 2,
            role: "assistant",
            content: "Hello! How can I help?",
            source: "web",
            search_used: false,
            citations: null,
            created_at: "2026-03-02T00:00:01Z",
          },
        ],
      });
    });

    await page.goto("/");

    // Type a message
    const input = page.getByPlaceholder(/ask|問/i);
    await input.fill("Hi");
    await input.press("Enter");

    // Wait for the AI response to appear
    await expect(page.getByText("Hello! How can I help?")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("shows streaming response with search and citations", async ({
    page,
  }) => {
    await page.route("**/api/chat", async (route) => {
      const sseBody = [
        'event: planner\ndata: {"needs_search":true,"reasoning":"temporal query","search_queries":["TSMC stock"],"query_type":"temporal"}\n\n',
        'event: searching\ndata: {"query":"TSMC stock","status":"searching"}\n\n',
        'event: searching\ndata: {"query":"TSMC stock","status":"done","results_count":3}\n\n',
        'event: chunk\ndata: {"content":"TSMC is trading at $180 [1]."}\n\n',
        'event: citations\ndata: {"citations":[{"index":1,"title":"TSMC Quote","url":"https://example.com","snippet":"TSMC at $180"}]}\n\n',
        'event: done\ndata: {}\n\n',
      ].join("");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sseBody,
      });
    });

    await page.route("**/api/conversations", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({ status: 200, json: [] });
      } else {
        await route.fulfill({
          status: 200,
          json: { id: "test-conv", title: "TSMC" },
        });
      }
    });

    await page.route("**/api/conversations/*/messages", async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 1,
            role: "user",
            content: "TSMC stock",
            source: "web",
            search_used: null,
            citations: null,
            created_at: "2026-03-02T00:00:00Z",
          },
          {
            id: 2,
            role: "assistant",
            content: "TSMC is trading at $180 [1].",
            source: "web",
            search_used: true,
            citations: [
              {
                index: 1,
                title: "TSMC Quote",
                url: "https://example.com",
                snippet: "TSMC at $180",
              },
            ],
            created_at: "2026-03-02T00:00:01Z",
          },
        ],
      });
    });

    await page.goto("/");

    const input = page.getByPlaceholder(/ask|問/i);
    await input.fill("TSMC stock");
    await input.press("Enter");

    // Wait for streamed answer
    await expect(page.getByText(/TSMC is trading/)).toBeVisible({
      timeout: 10_000,
    });

    // Citation card should appear
    await expect(page.getByText("TSMC Quote")).toBeVisible({ timeout: 5_000 });
  });
});
