"use client";

import type { ChatMessage, CitationItem, PlannerData, SearchingData } from "@/lib/types";
import { StreamingText } from "./StreamingText";
import { AgentThinking } from "./AgentThinking";
import { SearchProgress } from "./SearchProgress";
import { CitationList } from "./CitationList";

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
  const isUser = message.role === "user";

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
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div>
            {planner && <AgentThinking planner={planner} />}
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
