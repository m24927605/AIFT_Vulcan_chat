"use client";

import { useState } from "react";
import type { PlannerData } from "@/lib/types";

interface AgentThinkingProps {
  planner: PlannerData;
}

export function AgentThinking({ planner }: AgentThinkingProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors"
      >
        <span className="font-medium">
          {planner.needs_search ? "Searching the web" : "Answering directly"}
        </span>
        <span className="ml-auto">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-xs text-blue-600 dark:text-blue-400 space-y-1">
          <p>{planner.reasoning}</p>
          {planner.search_queries.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {planner.search_queries.map((q, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 bg-blue-100 dark:bg-blue-800 rounded-full text-xs"
                >
                  {q}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
