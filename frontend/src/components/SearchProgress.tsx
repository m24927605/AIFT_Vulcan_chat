"use client";

import type { SearchingData } from "@/lib/types";
import { useLocale } from "@/i18n";

interface SearchProgressProps {
  searches: SearchingData[];
}

export function SearchProgress({ searches }: SearchProgressProps) {
  const { t } = useLocale();

  if (searches.length === 0) return null;

  return (
    <div className="mb-3 space-y-1">
      {searches.map((s, i) => (
        <div
          key={`${s.query}-${i}`}
          className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
        >
          {s.status === "searching" ? (
            <span className="inline-block w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <span className="text-green-500">&#10003;</span>
          )}
          <span>
            {s.query}
            {s.status === "done" && s.results_count !== undefined && (
              <span className="ml-1 text-gray-400">
                ({s.results_count} {t.results})
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
