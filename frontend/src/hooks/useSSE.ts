import { useCallback, useRef } from "react";
import type {
  PlannerData,
  SearchingData,
  ChunkData,
  CitationsData,
} from "@/lib/types";

interface SSECallbacks {
  onPlanner?: (data: PlannerData) => void;
  onSearching?: (data: SearchingData) => void;
  onChunk?: (data: ChunkData) => void;
  onCitations?: (data: CitationsData) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      message: string,
      history: { role: string; content: string }[],
      callbacks: SSECallbacks
    ) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, history }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

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
                  case "done":
                    callbacks.onDone?.();
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

        callbacks.onDone?.();
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
