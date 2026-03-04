import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// Mock dependencies before importing useChat
vi.mock("@/hooks/useSSE", () => ({
  useSSE: () => ({
    sendMessage: vi.fn(),
    abort: vi.fn(),
  }),
}));

vi.mock("@/lib/api", () => ({
  fetchConversations: vi.fn().mockResolvedValue({ session_telegram_chat_id: null, conversations: [] }),
  createConversation: vi.fn().mockResolvedValue({ id: "test", title: "test" }),
  fetchMessages: vi.fn().mockResolvedValue([]),
  deleteConversationApi: vi.fn().mockResolvedValue(undefined),
  linkTelegram: vi.fn().mockResolvedValue(undefined),
  unlinkTelegram: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("uuid", () => ({
  v4: () => "mock-uuid-1234",
}));

// Mock localStorage
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
import { fetchConversations } from "@/lib/api";

beforeEach(() => {
  vi.clearAllMocks();
  localStorageMock.clear();
});

// Helper: render hook and wait for mount effects (fetchConversations) to settle
async function renderUseChatHook() {
  const hook = renderHook(() => useChat());
  await waitFor(() => {
    expect(fetchConversations).toHaveBeenCalled();
  });
  return hook;
}

describe("useChat", () => {
  it("newChat creates a new conversation with empty state", async () => {
    const { result } = await renderUseChatHook();

    act(() => {
      result.current.newChat();
    });

    expect(result.current.activeId).toBe("mock-uuid-1234");
    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
  });

  it("deleteConversation removes active conversation and resets state", async () => {
    const { deleteConversationApi } = await import("@/lib/api");
    const { result } = await renderUseChatHook();

    act(() => {
      result.current.newChat();
    });

    const id = result.current.activeId!;

    await act(async () => {
      await result.current.deleteConversation(id);
    });

    expect(deleteConversationApi).toHaveBeenCalledWith(id);
    expect(result.current.activeId).toBeNull();
    expect(result.current.messages).toEqual([]);
  });

  it("requestTelegramLink auto-creates conversation when none active", async () => {
    const { linkTelegram, createConversation } = await import("@/lib/api");
    vi.mocked(linkTelegram).mockResolvedValue({ status: "pending", code: "12345678", expires_in_seconds: 600 });
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const { result } = await renderUseChatHook();

    await act(async () => {
      result.current.requestTelegramLink();
    });

    expect(createConversation).toHaveBeenCalled();
    expect(linkTelegram).toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  it("requestTelegramLink starts polling and updates state when linked", async () => {
    vi.useFakeTimers();
    const CONV_ID = "existing-conv-1";
    const { linkTelegram, fetchConversations: fetchConvsMock, fetchMessages: fetchMsgsMock } =
      await import("@/lib/api");
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});

    // linkTelegram returns a code
    vi.mocked(linkTelegram).mockResolvedValueOnce({
      status: "ok",
      code: "12345678",
      expires_in_seconds: 600,
    });

    // Mount returns an existing unlinked conversation
    vi.mocked(fetchConvsMock).mockResolvedValueOnce({
      session_telegram_chat_id: null,
      conversations: [
        { id: CONV_ID, title: "Test", telegram_chat_id: null, created_at: "2026-01-01" },
      ],
    });
    vi.mocked(fetchMsgsMock).mockResolvedValue([]);

    const { result } = renderHook(() => useChat());

    // Flush initial mount effect (fetchConversations + loadConversation)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Verify the conversation loaded and is active but not linked
    expect(result.current.activeId).toBe(CONV_ID);
    expect(result.current.activeTelegramChatId).toBeNull();

    // Polling will now return the conversation as linked
    vi.mocked(fetchConvsMock).mockResolvedValue({
      session_telegram_chat_id: 99999,
      conversations: [
        { id: CONV_ID, title: "Test", telegram_chat_id: 99999, created_at: "2026-01-01" },
      ],
    });

    // Request link — triggers linkTelegram, then alert, then starts setInterval
    await act(async () => {
      result.current.requestTelegramLink();
      await vi.advanceTimersByTimeAsync(0); // flush linkTelegram promise
    });

    expect(linkTelegram).toHaveBeenCalledWith(CONV_ID);
    expect(alertSpy).toHaveBeenCalledOnce();

    // Advance past POLL_INTERVAL (3000ms) to trigger the first poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3500);
    });

    // Should now reflect the linked state
    expect(result.current.activeTelegramChatId).toBe(99999);

    alertSpy.mockRestore();
    vi.useRealTimers();
    // Reset mocks to defaults so they don't leak into subsequent tests
    vi.mocked(fetchConvsMock).mockResolvedValue({ session_telegram_chat_id: null, conversations: [] });
    vi.mocked(fetchMsgsMock).mockResolvedValue([]);
  });

  it("activeTelegramChatId reflects session-level state from API", async () => {
    const { fetchConversations: fetchConvsMock, fetchMessages: fetchMsgsMock } = await import("@/lib/api");

    vi.mocked(fetchConvsMock).mockResolvedValueOnce({
      session_telegram_chat_id: 12345,
      conversations: [
        { id: "c1", title: "Test", telegram_chat_id: 12345, created_at: "2026-01-01" },
      ],
    });
    vi.mocked(fetchMsgsMock).mockResolvedValue([]);

    const { result } = renderHook(() => useChat());
    await waitFor(() => {
      expect(result.current.activeTelegramChatId).toBe(12345);
    });

    // Reset mocks
    vi.mocked(fetchConvsMock).mockResolvedValue({ session_telegram_chat_id: null, conversations: [] });
    vi.mocked(fetchMsgsMock).mockResolvedValue([]);
  });

  it("unlinkTelegramLink alerts when no active conversation", async () => {
    const { unlinkTelegram } = await import("@/lib/api");
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    const { result } = await renderUseChatHook();

    act(() => {
      result.current.unlinkTelegramLink();
    });

    expect(unlinkTelegram).not.toHaveBeenCalled();
    expect(alertSpy).toHaveBeenCalledOnce();
    alertSpy.mockRestore();
  });
});
