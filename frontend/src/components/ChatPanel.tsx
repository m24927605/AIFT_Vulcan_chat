"use client";

import { useEffect, useRef } from "react";
import type { ChatMessage, CitationItem, PlannerData, SearchingData, VerificationData } from "@/lib/types";
import { useLocale } from "@/i18n";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";

interface ChatPanelProps {
  messages: ChatMessage[];
  isLoading: boolean;
  streamingContent: string;
  planner: PlannerData | null;
  searchStatus: SearchingData[];
  citations: CitationItem[];
  verification: VerificationData | null;
  onSend: (message: string) => void;
}

export function ChatPanel({
  messages,
  isLoading,
  streamingContent,
  planner,
  searchStatus,
  citations,
  verification,
  onSend,
}: ChatPanelProps) {
  const { t } = useLocale();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const showEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {showEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-gray-400 dark:text-gray-500">
            <h2 className="text-2xl font-semibold mb-2">{t.emptyTitle}</h2>
            <p className="text-sm">{t.emptySubtitle}</p>
          </div>
        )}
        {messages.map((msg, i) => {
          const isLast = i === messages.length - 1;
          const isAssistantStreaming =
            isLast && msg.role === "assistant" && isLoading;

          // Show verification only on the latest assistant message, not while streaming
          const showVerification =
            isLast && msg.role === "assistant" && !isLoading;

          return (
            <MessageBubble
              key={i}
              message={msg}
              isStreaming={isAssistantStreaming}
              streamingContent={isAssistantStreaming ? streamingContent : undefined}
              citations={msg.role === "assistant" ? (msg.citations || []) : []}
              verification={showVerification ? verification : null}
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
      <div className="px-4 py-2 text-center text-[10px] leading-tight text-gray-400 dark:text-gray-600 border-t border-gray-100 dark:border-gray-800">
        {t.disclaimer}
      </div>
    </div>
  );
}
