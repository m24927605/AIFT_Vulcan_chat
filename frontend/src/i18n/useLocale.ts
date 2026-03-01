"use client";

import { useMemo } from "react";
import { translations, type Locale } from "./translations";

function detectLocale(): Locale {
  if (typeof navigator === "undefined") return "en";
  const lang = navigator.language;
  if (lang.startsWith("zh")) return "zh-TW";
  return "en";
}

export function useLocale() {
  const locale = useMemo(detectLocale, []);
  const t = useMemo(() => translations[locale], [locale]);
  return { locale, t };
}
