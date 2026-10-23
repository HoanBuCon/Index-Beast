// Ngôn ngữ giao diện độc lập với câu hỏi và nội dung trả lời; không tự dịch dữ liệu người dùng.
// Phụ trách: TV4 · Giao diện Việt / Anh
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import translations from "./translations.json";

type Language = "vi" | "en";
const dictionary: Record<string, string> = translations;
const key = "indexbeast.language";
const LanguageContext = createContext({
  language: "vi" as Language,
  setLanguage: (_language: Language) => {},
  t: (text: string) => text,
});
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    try {
      return localStorage.getItem(key) === "en" ? "en" : "vi";
    } catch {
      return "vi";
    }
  });
  useEffect(() => {
    document.documentElement.lang = language;
    document.title =
      language === "vi" ? "Index Beast — Hỏi đáp lore Elden Ring" : "Index Beast — Elden Ring lore archive";
    try {
      localStorage.setItem(key, language);
    } catch {
      /* Chế độ riêng tư vẫn cho phép đổi ngôn ngữ trong phiên. */
    }
  }, [language]);
  function t(text: string) {
    if (language === "vi") return text;
    const normalized = text.replace(/\s+/g, " ").trim();
    const retry = /^(.*) Thử lại sau (.*)\.$/.exec(normalized);
    if (retry) return `${dictionary[retry[1]] ?? retry[1]} Retry after ${retry[2]}.`;
    return dictionary[normalized] ?? text;
  }
  return <LanguageContext.Provider value={{ language, setLanguage, t }}>{children}</LanguageContext.Provider>;
}
export function useLanguage() {
  return useContext(LanguageContext);
}
