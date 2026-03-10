"use client";

import { useState } from "react";
import type { VerificationData } from "@/lib/types";
import { useLocale } from "@/i18n";

interface VerificationBadgeProps {
  verification: VerificationData | null;
}

export function VerificationBadge({ verification }: VerificationBadgeProps) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(true);

  if (!verification) return null;

  const pct = `${Math.round(verification.confidence * 100)}%`;

  if (verification.is_consistent) {
    return (
      <div className="mt-3">
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300">
          <span>✓</span>
          <span>{t.verificationConsistent}</span>
          <span className="text-green-500 dark:text-green-400">({pct})</span>
        </span>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/30 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/50 transition-colors"
      >
        <span>⚠</span>
        <span className="font-medium">{t.verificationInconsistent}</span>
        <span className="text-amber-500 dark:text-amber-400">({pct})</span>
        <span className="ml-auto">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2.5 text-xs text-amber-700 dark:text-amber-300 space-y-1.5">
          {verification.issues.length > 0 && (
            <ul className="list-disc list-inside space-y-0.5">
              {verification.issues.map((issue, i) => (
                <li key={i}>{issue}</li>
              ))}
            </ul>
          )}
          {verification.suggestion && (
            <p className="text-amber-600 dark:text-amber-400">
              <span className="font-medium">{t.verificationSuggestion}:</span>{" "}
              {verification.suggestion}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
