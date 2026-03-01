"use client";

import type { CitationItem } from "@/lib/types";
import { useLocale } from "@/i18n";
import { CitationCard } from "./CitationCard";

interface CitationListProps {
  citations: CitationItem[];
}

export function CitationList({ citations }: CitationListProps) {
  const { t } = useLocale();

  if (citations.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
        {t.sources}
      </p>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {citations.map((c) => (
          <CitationCard key={c.index} citation={c} />
        ))}
      </div>
    </div>
  );
}
