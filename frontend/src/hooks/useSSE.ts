import { useCallback, useRef } from "react";
import type {
  PlannerData,
  SearchingData,
  ChunkData,
  CitationsData,
} from "@/lib/types";
import { getCsrfToken } from "@/lib/csrf";

interface SSECallbacks {
  onPlanner?: (data: PlannerData) => void;
  onSearching?: (data: SearchingData) => void;
  onChunk?: (data: ChunkData) => void;
  onCitations?: (data: CitationsData) => void;
  onSearchFailed?: (data: { message: string }) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      message: string,
      history: { role: string; content: string }[],
      callbacks: SSECallbacks,
      conversationId?: string
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const body: Record<string, unknown> = { message, history };
        if (conversationId) {
          body.conversation_id = conversationId;
        }
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
          body: JSON.stringify(body),
          credentials: "include",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let doneEmitted = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let currentEvent = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const rawData = line.slice(6);
              try {
                const data = JSON.parse(rawData);
                switch (currentEvent) {
                  case "planner":
                    callbacks.onPlanner?.(data);
                    break;
                  case "searching":
                    callbacks.onSearching?.(data);
                    break;
                  case "chunk":
                    callbacks.onChunk?.(data);
                    break;
                  case "citations":
                    callbacks.onCitations?.(data);
                    break;
                  case "search_failed":
                    callbacks.onSearchFailed?.(data);
                    break;
                  case "done":
                    if (!doneEmitted) { doneEmitted = true; callbacks.onDone?.(); }
                    break;
                  case "error":
                    callbacks.onError?.(data.message);
                    break;
                }
              } catch {
                // skip malformed JSON
              }
              currentEvent = "";
            }
          }
        }

        if (!doneEmitted) { doneEmitted = true; callbacks.onDone?.(); }
      } catch (err) {
        if (err instanceof Error && err.name !== "AbortError") {
          callbacks.onError?.(err.message);
        }
      }
    },
    []
  );

  const abort = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { sendMessage, abort };
}
