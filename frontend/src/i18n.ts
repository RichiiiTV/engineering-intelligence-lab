import { useSyncExternalStore } from "react";
import english from "./messages.en";

export type Language = "de" | "en";
const STORAGE_KEY = "eil-language-v1";
function savedLanguage(): Language {
  try {
    return localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "de";
  } catch {
    return "de";
  }
}
let language = savedLanguage();
const germanByEnglish = new Map(
  Object.entries(english).map(([de, en]) => [en, de]),
);
const listeners = new Set<() => void>();
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};
export const getLanguage = () => language;
export const getLocale = () => (language === "de" ? "de-DE" : "en-GB");
export function setLanguage(value: string) {
  if (value !== "de" && value !== "en") return;
  if (typeof document !== "undefined") document.documentElement.lang = value;
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* Private storage may be disabled. */
  }
  if (language === value) return;
  language = value;
  for (const notify of listeners) notify();
}
export function useLanguage() {
  return useSyncExternalStore(subscribe, getLanguage, () => "de" as Language);
}
/** Translate authored UI copy and known feedback; never uploaded/model content. */
export function t(copy: string): string {
  if (language === "en")
    return Object.hasOwn(english, copy) ? english[copy] : copy;
  return Object.hasOwn(english, copy)
    ? copy
    : (germanByEnglish.get(copy) ?? copy);
}
/** Translate template literals without inspecting or translating interpolated user data. */
export function tr(parts: TemplateStringsArray, ...values: unknown[]): string {
  return parts.reduce(
    (text, part, index) =>
      text + t(part) + (index < values.length ? String(values[index]) : ""),
    "",
  );
}
if (typeof document !== "undefined") document.documentElement.lang = language;
if (typeof window !== "undefined")
  window.addEventListener("storage", (event) => {
    if (event.key === STORAGE_KEY)
      setLanguage(event.newValue === "en" ? "en" : "de");
  });
