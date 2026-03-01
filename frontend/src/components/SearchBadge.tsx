"use client";

import { useLocale } from "@/i18n";

interface SearchBadgeProps {
  searchUsed: boolean;
}

export function SearchBadge({ searchUsed }: SearchBadgeProps) {
  const { t } = useLocale();

  return (
    <div className="mb-2">
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
          searchUsed
            ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
            : "bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
        }`}
      >
        {searchUsed ? "🔍" : "💬"}{" "}
        {searchUsed ? t.searchedWeb : t.answeredDirectly}
      </span>
    </div>
  );
}
