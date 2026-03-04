"use client";

import type { ChatMessage, CitationItem, PlannerData, SearchingData } from "@/lib/types";
import { useLocale } from "@/i18n";
import { StreamingText } from "./StreamingText";
import { AgentThinking } from "./AgentThinking";
import { SearchProgress } from "./SearchProgress";
import { CitationList } from "./CitationList";
import { SearchBadge } from "./SearchBadge";

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
  streamingContent?: string;
  planner?: PlannerData | null;
  searchStatus?: SearchingData[];
  citations?: CitationItem[];
}

export function MessageBubble({
  message,
  isStreaming,
  streamingContent,
  planner,
  searchStatus = [],
  citations = [],
}: MessageBubbleProps) {
  const { t } = useLocale();
  const isUser = message.role === "user";
  const isTelegram = message.source === "telegram";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] ${
          isUser
            ? "bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2.5"
            : "bg-transparent"
        }`}
      >
        {isUser ? (
          <div>
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
            {isTelegram && (
              <span className="text-[10px] opacity-70 mt-0.5 block text-right">
                {t.viaTelegram}
              </span>
            )}
          </div>
        ) : (
          <div>
            {isTelegram && (
              <span className="inline-block text-[10px] text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded mb-1">
                {t.viaTelegram}
              </span>
            )}
            {isStreaming && planner && <AgentThinking planner={planner} />}
            {!isStreaming && message.searchUsed !== undefined && (
              <SearchBadge searchUsed={message.searchUsed} />
            )}
            {searchStatus.length > 0 && (
              <SearchProgress searches={searchStatus} />
            )}
            <StreamingText
              content={isStreaming ? (streamingContent || "") : message.content}
              isStreaming={isStreaming}
            />
            {!isStreaming && <CitationList citations={citations} />}
          </div>
        )}
      </div>
    </div>
  );
}
