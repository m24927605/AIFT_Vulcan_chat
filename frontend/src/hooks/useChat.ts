"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { useSSE } from "./useSSE";
import {
  fetchConversations,
  createConversation,
  fetchMessages,
  deleteConversationApi,
  linkTelegram,
  unlinkTelegram,
} from "@/lib/api";
import type {
  ChatMessage,
  CitationItem,
  PlannerData,
  SearchingData,
  Conversation,
} from "@/lib/types";

interface ChatState {
  isLoading: boolean;
  messages: ChatMessage[];
  citations: CitationItem[];
  planner: PlannerData | null;
  searchStatus: SearchingData[];
  streamingContent: string;
}

const POLL_INTERVAL = 3000;

const INITIAL_CHAT_STATE: ChatState = {
  isLoading: false,
  messages: [],
  citations: [],
  planner: null,
  searchStatus: [],
  streamingContent: "",
};

function mapApiMessage(m: {
  id: number;
  role: string;
  content: string;
  source: string;
  search_used: boolean | null;
  citations: CitationItem[] | null;
}): ChatMessage {
  return {
    role: m.role as "user" | "assistant",
    content: m.content,
    source: m.source as "web" | "telegram",
    id: m.id,
    searchUsed: m.search_used ?? undefined,
    citations: m.citations ?? undefined,
  };
}

function updateMaxId(
  ref: React.MutableRefObject<number>,
  msgs: { id: number }[],
) {
  if (msgs.length > 0) {
    ref.current = Math.max(...msgs.map((m) => m.id));
  }
}

export function useChat() {
  const { sendMessage: sseMessage, abort } = useSSE();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveIdRaw] = useState<string | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const [sessionTelegramChatId, setSessionTelegramChatId] = useState<number | null>(null);

  // Wrap setActiveId to persist to localStorage
  const setActiveId = useCallback((id: string | null) => {
    setActiveIdRaw(id);
    if (id) {
      localStorage.setItem("activeConversationId", id);
    } else {
      localStorage.removeItem("activeConversationId");
    }
  }, []);
  const maxMessageIdRef = useRef<number>(0);
  const persistedRef = useRef(false); // tracks if activeId conversation exists on backend
  const [state, setState] = useState<ChatState>(INITIAL_CHAT_STATE);
  const isLoadingRef = useRef(false);

  // Keep refs in sync
  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    isLoadingRef.current = state.isLoading;
  }, [state.isLoading]);

  // Load conversations from backend on mount, restore last active conversation
  useEffect(() => {
    fetchConversations()
      .then(async (result) => {
        const convs = result.conversations;
        setSessionTelegramChatId(result.session_telegram_chat_id);
        const mapped = convs.map((c) => ({
          id: c.id,
          title: c.title,
          messages: [],
          createdAt: c.created_at,
          telegram_chat_id: c.telegram_chat_id,
        }));
        setConversations(mapped);
        // Sync known IDs with backend reality
        const serverIds = convs.map((c) => c.id);
        localStorage.setItem("conversationIds", JSON.stringify(serverIds));

        // Restore last active conversation if it still exists; otherwise choose first.
        const savedId = localStorage.getItem("activeConversationId");
        const restoreId =
          (savedId && serverIds.includes(savedId) && savedId) ||
          (mapped[0]?.id ?? null);
        if (restoreId) {
          const conv = mapped.find((c) => c.id === restoreId);
          if (conv) {
            setActiveId(restoreId);
            persistedRef.current = true;
            try {
              const msgs = await fetchMessages(restoreId, undefined);
              updateMaxId(maxMessageIdRef, msgs);
              setState((prev) => ({ ...prev, messages: msgs.map(mapApiMessage) }));
            } catch (err) {
              console.error("Failed to restore conversation messages:", err);
            }
          }
        }
      })
      .catch((err) => console.error("Failed to fetch conversations:", err));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Polling for new messages (picks up Telegram messages)
  // Pauses when tab is hidden to avoid unnecessary requests
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;

    const poll = async () => {
      const convId = activeIdRef.current;
      if (!convId || isLoadingRef.current || !persistedRef.current) return;

      try {
        const newMsgs = await fetchMessages(convId, maxMessageIdRef.current || undefined);
        if (newMsgs.length > 0 && activeIdRef.current === convId) {
          updateMaxId(maxMessageIdRef, newMsgs);
          const mapped = newMsgs.map(mapApiMessage);

          setState((prev) => {
            // Deduplicate by message ID
            const existingIds = new Set(
              prev.messages.filter((m) => m.id != null).map((m) => m.id)
            );
            const trulyNew = mapped.filter((m) => !existingIds.has(m.id));
            if (trulyNew.length === 0) return prev;
            return { ...prev, messages: [...prev.messages, ...trulyNew] };
          });
        }
      } catch {
        // polling errors are non-critical
      }
    };

    const startPolling = () => {
      if (!interval) interval = setInterval(poll, POLL_INTERVAL);
    };

    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    startPolling();
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);

  const linkPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const linkTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup link polling on unmount
  useEffect(() => {
    return () => {
      if (linkPollRef.current) {
        clearInterval(linkPollRef.current);
        linkPollRef.current = null;
      }
      if (linkTimeoutRef.current) {
        clearTimeout(linkTimeoutRef.current);
        linkTimeoutRef.current = null;
      }
    };
  }, []);

  const requestTelegramLink = useCallback(async () => {
    let convId = activeIdRef.current;
    if (!convId) {
      convId = newChat();
    }
    if (!persistedRef.current) {
      await createConversation(convId, "New Chat");
      setConversations((prev) => [
        { id: convId!, title: "New Chat", messages: [], telegram_chat_id: null, createdAt: new Date().toISOString() },
        ...prev,
      ]);
      persistedRef.current = true;
    }
    linkTelegram(convId)
      .then((result) => {
        window.alert(
          `驗證碼：${result.code}\n請開啟 Telegram Bot，按「Start Linking／開始綁定」，再用數字鍵盤輸入 8 碼。（${Math.floor(result.expires_in_seconds / 60)} 分鐘內有效）`
        );
        // Poll for link completion until session telegram_chat_id is set
        if (linkPollRef.current) clearInterval(linkPollRef.current);
        if (linkTimeoutRef.current) clearTimeout(linkTimeoutRef.current);
        linkPollRef.current = setInterval(async () => {
          try {
            const result = await fetchConversations();
            if (result.session_telegram_chat_id) {
              setSessionTelegramChatId(result.session_telegram_chat_id);
              setConversations((prev) =>
                prev.map((c) => ({
                  ...c,
                  telegram_chat_id: result.session_telegram_chat_id,
                }))
              );
              if (linkPollRef.current) {
                clearInterval(linkPollRef.current);
                linkPollRef.current = null;
              }
            }
          } catch {
            // polling errors are non-critical
          }
        }, POLL_INTERVAL);
        // Stop polling after code expires
        linkTimeoutRef.current = setTimeout(() => {
          if (linkPollRef.current) {
            clearInterval(linkPollRef.current);
            linkPollRef.current = null;
          }
          linkTimeoutRef.current = null;
        }, result.expires_in_seconds * 1000);
      })
      .catch((err) => console.error("Telegram link request failed:", err));
  }, []);

  const unlinkTelegramLink = useCallback(() => {
    const convId = activeIdRef.current;
    if (!convId) {
      window.alert("目前沒有可取消連結的對話。");
      return;
    }
    unlinkTelegram(convId).catch((err) =>
      console.error("Telegram unlink failed:", err)
    );
    setSessionTelegramChatId(null);
    setConversations((prev) =>
      prev.map((c) => ({ ...c, telegram_chat_id: null }))
    );
  }, []);

  const newChat = useCallback(() => {
    const id = uuidv4();
    setActiveId(id);
    maxMessageIdRef.current = 0;
    persistedRef.current = false;
    setState(INITIAL_CHAT_STATE);
    return id;
  }, []);

  const loadConversation = useCallback(async (conv: Conversation) => {
    setActiveId(conv.id);
    maxMessageIdRef.current = 0;
    persistedRef.current = true; // loaded from backend, so it exists

    try {
      const msgs = await fetchMessages(conv.id, undefined);
      updateMaxId(maxMessageIdRef, msgs);
      setState({ ...INITIAL_CHAT_STATE, messages: msgs.map(mapApiMessage) });
    } catch (err) {
      console.error("Failed to load messages:", err);
      setState(INITIAL_CHAT_STATE);
    }
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMessage: ChatMessage = { role: "user", content, source: "web" };

      let currentId = activeId;
      if (!currentId) {
        currentId = uuidv4();
        setActiveId(currentId);
      }

      // Create conversation on backend if it doesn't exist yet
      if (!persistedRef.current) {
        const title =
          content.length > 30 ? content.slice(0, 30) + "..." : content;
        try {
          await createConversation(currentId, title);
          persistedRef.current = true;
          // Track conversation ID locally
          const ids: string[] = JSON.parse(localStorage.getItem("conversationIds") || "[]");
          if (!ids.includes(currentId)) {
            ids.push(currentId);
            localStorage.setItem("conversationIds", JSON.stringify(ids));
          }
        } catch (err) {
          console.error("Failed to create conversation:", err);
        }
      }

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isLoading: true,
        planner: null,
        searchStatus: [],
        streamingContent: "",
        citations: [],
      }));

      let fullContent = "";
      let finalCitations: CitationItem[] = [];
      let searchUsed: boolean | undefined;

      await sseMessage(
        content,
        [], // backend loads history from DB
        {
          onPlanner: (data) => {
            searchUsed = data.needs_search;
            setState((prev) => ({ ...prev, planner: data }));
          },
          onSearching: (data) => {
            setState((prev) => ({
              ...prev,
              searchStatus: [
                ...prev.searchStatus.filter(
                  (s) => !(s.query === data.query && data.status === "done")
                ),
                data,
              ],
            }));
          },
          onSearchFailed: (data) => {
            // Prepend warning to streaming content
            const warning = `⚠️ ${data.message}\n\n`;
            fullContent = warning + fullContent;
            setState((prev) => ({
              ...prev,
              streamingContent: fullContent,
            }));
          },
          onChunk: (data) => {
            fullContent += data.content;
            setState((prev) => ({
              ...prev,
              streamingContent: fullContent,
            }));
          },
          onCitations: (data) => {
            finalCitations = data.citations;
            setState((prev) => ({
              ...prev,
              citations: data.citations,
            }));
          },
          onDone: () => {
            const assistantMessage: ChatMessage = {
              role: "assistant",
              content: fullContent,
              searchUsed,
              citations: finalCitations.length > 0 ? finalCitations : undefined,
              source: "web",
            };

            // Fetch only new messages from backend to get correct IDs
            fetchMessages(currentId!, maxMessageIdRef.current || undefined).then((msgs) => {
              if (msgs.length > 0) {
                updateMaxId(maxMessageIdRef, msgs);
                setState((prev) => ({
                  ...prev,
                  messages: [...prev.messages.filter((m) => m.id != null), ...msgs.map(mapApiMessage)],
                  isLoading: false,
                  streamingContent: "",
                }));
              } else {
                // Fallback: use local messages
                setState((prev) => ({
                  ...prev,
                  messages: [...prev.messages, assistantMessage],
                  isLoading: false,
                  streamingContent: "",
                }));
              }
            }).catch(() => {
              // Fallback: use local messages
              setState((prev) => ({
                ...prev,
                messages: [...prev.messages, assistantMessage],
                isLoading: false,
                streamingContent: "",
              }));
            });

            setConversations((prev) => {
              const title =
                content.length > 30
                  ? content.slice(0, 30) + "..."
                  : content;
              const existing = prev.find((c) => c.id === currentId);
              if (existing) {
                return prev;
              }
              return [
                {
                  id: currentId!,
                  title,
                  messages: [],
                  createdAt: new Date().toISOString(),
                },
                ...prev,
              ];
            });
          },
          onError: (error) => {
            setState((prev) => ({
              ...prev,
              isLoading: false,
              streamingContent: "",
            }));
            console.error("Chat error:", error);
          },
        },
        currentId
      );
    },
    [activeId, sseMessage]
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        await deleteConversationApi(id);
      } catch (err) {
        console.error("Failed to delete conversation:", err);
        return;
      }
      // Remove from local tracking only after backend confirms deletion
      const ids: string[] = JSON.parse(localStorage.getItem("conversationIds") || "[]");
      localStorage.setItem("conversationIds", JSON.stringify(ids.filter((i) => i !== id)));
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
        maxMessageIdRef.current = 0;
        persistedRef.current = false;
        setState(INITIAL_CHAT_STATE);
      }
    },
    [activeId]
  );

  return {
    ...state,
    conversations,
    activeId,
    activeTelegramChatId: sessionTelegramChatId,
    requestTelegramLink,
    unlinkTelegramLink,
    sendMessage,
    newChat,
    loadConversation,
    deleteConversation,
    abort,
  };
}
