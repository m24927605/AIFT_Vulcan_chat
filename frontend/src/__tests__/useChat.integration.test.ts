/**
 * Integration test: sendMessage → SSE callbacks → final state
 *
 * Simulates a complete chat flow by providing a mock useSSE that
 * invokes all SSE callbacks (planner → searching → chunks → citations → done)
 * inline, then verifies the final useChat state matches expectations.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// Simulate full SSE flow: planner → searching → chunks → citations → done
const mockSseMessage = vi.fn(
  async (
    _message: string,
    _history: unknown[],
    callbacks: Record<string, (...args: unknown[]) => void>,
    _conversationId?: string
  ) => {
    callbacks.onPlanner?.({
      needs_search: true,
      reasoning: "Temporal question about stock price",
      search_queries: ["TSMC stock price"],
      query_type: "temporal",
    });
    callbacks.onSearching?.({ query: "TSMC stock price", status: "searching" });
    callbacks.onSearching?.({
      query: "TSMC stock price",
      status: "done",
      results_count: 3,
    });
    callbacks.onChunk?.({ content: "TSMC stock is " });
    callbacks.onChunk?.({ content: "$150 [1]." });
    callbacks.onCitations?.({
      citations: [
        {
          index: 1,
          title: "TSMC Quote",
          url: "https://finance.example.com/tsmc",
          snippet: "TSMC trading at $150",
        },
      ],
    });
    callbacks.onDone?.();
  }
);

vi.mock("@/hooks/useSSE", () => ({
  useSSE: () => ({
    sendMessage: mockSseMessage,
    abort: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  fetchConversations: vi.fn().mockResolvedValue({ session_telegram_chat_id: null, conversations: [] }),
  createConversation: vi.fn().mockResolvedValue({ id: "test", title: "test" }),
  fetchMessages: vi.fn().mockResolvedValue([
    {
      id: 1,
      role: "user",
      content: "台積電股價",
      source: "web",
      search_used: null,
      citations: null,
      created_at: "2026-03-02T00:00:00Z",
    },
    {
      id: 2,
      role: "assistant",
      content: "TSMC stock is $150 [1].",
      source: "web",
      search_used: true,
      citations: [
        {
          index: 1,
          title: "TSMC Quote",
          url: "https://finance.example.com/tsmc",
          snippet: "TSMC trading at $150",
        },
      ],
      created_at: "2026-03-02T00:00:01Z",
    },
  ]),
  deleteConversationApi: vi.fn().mockResolvedValue(undefined),
  linkTelegram: vi.fn().mockResolvedValue(undefined),
  unlinkTelegram: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("uuid", () => ({
  v4: () => "integration-test-uuid",
}));

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();
vi.stubGlobal("localStorage", localStorageMock);

import { useChat } from "@/hooks/useChat";
import { fetchConversations, createConversation, fetchMessages } from "@/lib/api";

beforeEach(() => {
  vi.clearAllMocks();
  localStorageMock.clear();
});

async function renderUseChatHook() {
  const hook = renderHook(() => useChat());
  await waitFor(() => {
    expect(fetchConversations).toHaveBeenCalled();
  });
  return hook;
}

describe("useChat integration: sendMessage → SSE → state", () => {
  it("full chat flow: planner → search → stream → citations → final state", async () => {
    const { result } = await renderUseChatHook();

    // Send a message (triggers mock SSE flow)
    await act(async () => {
      await result.current.sendMessage("台積電股價");
    });

    // Wait for onDone callback to fetch messages from backend and update state
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify conversation was created on backend
    expect(createConversation).toHaveBeenCalledWith(
      "integration-test-uuid",
      "台積電股價"
    );

    // Verify SSE sendMessage was called with correct args
    expect(mockSseMessage).toHaveBeenCalledWith(
      "台積電股價",
      [],
      expect.any(Object),
      "integration-test-uuid"
    );

    // Verify planner data was captured
    expect(result.current.planner).toEqual({
      needs_search: true,
      reasoning: "Temporal question about stock price",
      search_queries: ["TSMC stock price"],
      query_type: "temporal",
    });

    // Verify citations were captured
    expect(result.current.citations).toEqual([
      {
        index: 1,
        title: "TSMC Quote",
        url: "https://finance.example.com/tsmc",
        snippet: "TSMC trading at $150",
      },
    ]);

    // Verify final messages came from backend (fetchMessages)
    expect(fetchMessages).toHaveBeenCalledWith("integration-test-uuid", undefined);
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "台積電股價",
    });
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "TSMC stock is $150 [1].",
      searchUsed: true,
    });

    // Verify streaming content was cleared after done
    expect(result.current.streamingContent).toBe("");

    // Verify conversation appeared in sidebar
    expect(result.current.conversations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "integration-test-uuid",
          title: "台積電股價",
        }),
      ])
    );
  });
});
