import { create } from "zustand";
import { persist } from "zustand/middleware";
import i18n from "../i18n/config";

type Language = "ar" | "en";

interface LanguageState {
  language: Language;
  setLanguage: (lang: Language) => void;
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set) => ({
      language: "ar",
      setLanguage: (lang) => {
        i18n.changeLanguage(lang);
        document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
        document.documentElement.lang = lang;
        set({ language: lang });
      },
    }),
    { name: "hr-language" }
  )
);
