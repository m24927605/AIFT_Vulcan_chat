"use client";

import type { CitationItem } from "@/lib/types";

function safeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "http:" || parsed.protocol === "https:") return url;
  } catch {
    // invalid URL
  }
  return "#";
}

interface CitationCardProps {
  citation: CitationItem;
}

export function CitationCard({ citation }: CitationCardProps) {
  const domain = (() => {
    try {
      return new URL(citation.url).hostname.replace("www.", "");
    } catch {
      return citation.url;
    }
  })();

  return (
    <a
      href={safeUrl(citation.url)}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col gap-1 p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 hover:border-blue-300 dark:hover:border-blue-600 transition-colors min-w-[140px] sm:min-w-[180px] max-w-[200px] sm:max-w-[240px]"
    >
      <div className="flex items-center gap-1.5">
        <span className="flex items-center justify-center w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-xs font-bold">
          {citation.index}
        </span>
        <span className="text-xs text-gray-400 truncate">{domain}</span>
      </div>
      <span className="text-xs font-medium text-gray-700 dark:text-gray-300 line-clamp-2">
        {citation.title}
      </span>
    </a>
  );
}
