"use client";

import ReactMarkdown from "react-markdown";

interface StreamingTextProps {
  content: string;
  isStreaming?: boolean;
}

export function StreamingText({ content, isStreaming }: StreamingTextProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none overflow-hidden">
      <ReactMarkdown>{content}</ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-0.5" />
      )}
    </div>
  );
}
