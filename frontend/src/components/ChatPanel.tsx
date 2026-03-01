"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage, CitationItem, PlannerData, SearchingData } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  streamingContent: string;
  planner: PlannerData | null;
  searchStatus: SearchingData[];
  citations: CitationItem[];
  onSend: (message: string) => void;
}

export function ChatPanel({
  messages,
  isLoading,
  streamingContent,
  planner,
  searchStatus,
  citations,
  onSend,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const showEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {showEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <h2 className="text-2xl font-semibold mb-2">Web Search Chatbot</h2>
            <p className="text-sm">Ask me anything. I can search the web for the latest info.</p>
          </div>
        )}
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isAssistantStreaming =
            isLast && msg.role === "assistant" && isLoading;

          return (
            <MessageBubble
              key={i}
              message={msg}
              isStreaming={isAssistantStreaming}
              streamingContent={isAssistantStreaming ? streamingContent : undefined}
              citations={isLast && msg.role === "assistant" ? citations : []}
            />
          );
        })}

        {isLoading && messages[messages.length - 1]?.role === "user" && (
          <MessageBubble
            message={{ role: "assistant", content: "" }}
            isStreaming={true}
            streamingContent={streamingContent}
            planner={planner}
            searchStatus={searchStatus}
            citations={[]}
          />
        )}

        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={onSend} disabled={isLoading} />
    </div>
  );
}
