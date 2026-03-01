"use client";

import { useState, useCallback } from "react";
import { v4 as uuidv4 } from "uuid";
import { useSSE } from "./useSSE";
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

export function useChat() {
  const { sendMessage: sseMessage, abort } = useSSE();
  const [conversations, setConversations] = useState<Conversation[]>(() => {
    if (typeof window === "undefined") return [];
    const saved = localStorage.getItem("conversations");
    return saved ? JSON.parse(saved) : [];
  });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [state, setState] = useState<ChatState>({
    isLoading: false,
    messages: [],
    citations: [],
    planner: null,
    searchStatus: [],
    streamingContent: "",
  });

  const saveConversations = useCallback((convs: Conversation[]) => {
    setConversations(convs);
    localStorage.setItem("conversations", JSON.stringify(convs));
  }, []);

  const newChat = useCallback(() => {
    const id = uuidv4();
    setActiveId(id);
    setState({
      isLoading: false,
      messages: [],
      citations: [],
      planner: null,
      searchStatus: [],
      streamingContent: "",
    });
    return id;
  }, []);

  const loadConversation = useCallback((conv: Conversation) => {
    setActiveId(conv.id);
    setState({
      isLoading: false,
      messages: conv.messages,
      citations: conv.citations,
      planner: null,
      searchStatus: [],
      streamingContent: "",
    });
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMessage: ChatMessage = { role: "user", content };
      const currentMessages = [...state.messages, userMessage];

      setState((prev) => ({
        ...prev,
        messages: currentMessages,
        isLoading: true,
        planner: null,
        searchStatus: [],
        streamingContent: "",
        citations: [],
      }));

      let fullContent = "";
      let finalCitations: CitationItem[] = [];
      const currentId = activeId || newChat();

      await sseMessage(
        content,
        currentMessages.slice(0, -1).map((m) => ({
          role: m.role,
          content: m.content,
        })),
        {
          onPlanner: (data) => {
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
            };
            const updatedMessages = [...currentMessages, assistantMessage];

            setState((prev) => ({
              ...prev,
              messages: updatedMessages,
              isLoading: false,
              streamingContent: "",
            }));

            setConversations((prev) => {
              const title =
                content.length > 30
                  ? content.slice(0, 30) + "..."
                  : content;
              const existing = prev.find((c) => c.id === currentId);
              let updated: Conversation[];
              if (existing) {
                updated = prev.map((c) =>
                  c.id === currentId
                    ? {
                        ...c,
                        messages: updatedMessages,
                        citations: finalCitations,
                      }
                    : c
                );
              } else {
                updated = [
                  {
                    id: currentId,
                    title,
                    messages: updatedMessages,
                    citations: finalCitations,
                    createdAt: new Date().toISOString(),
                  },
                  ...prev,
                ];
              }
              localStorage.setItem("conversations", JSON.stringify(updated));
              return updated;
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
        }
      );
    },
    [state.messages, activeId, sseMessage, newChat]
  );

  const deleteConversation = useCallback(
    (id: string) => {
      const updated = conversations.filter((c) => c.id !== id);
      saveConversations(updated);
      if (activeId === id) {
        setActiveId(null);
        setState({
          isLoading: false,
          messages: [],
          citations: [],
          planner: null,
          searchStatus: [],
          streamingContent: "",
        });
      }
    },
    [conversations, activeId, saveConversations]
  );

  return {
    ...state,
    conversations,
    activeId,
    sendMessage,
    newChat,
    loadConversation,
    deleteConversation,
    abort,
  };
}
