import { useTranslation } from "react-i18next";
import { useAuthStore } from "../../store/auth";
import { useLanguageStore } from "../../store/language";

export default function Header() {
  const { t } = useTranslation();
  const { employee, logout } = useAuthStore();
  const { language, setLanguage } = useLanguageStore();

  const displayName = language === "ar" ? employee?.name_ar : employee?.name_en;
  const initial = displayName?.charAt(0) ?? "?";

  return (
    <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-slate-900/80 backdrop-blur shrink-0">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-lg select-none">
          🤖
        </div>
        <div>
          <h1 className="font-bold text-base leading-tight">{t("app.name")}</h1>
          <p className="text-xs text-slate-400">{t("app.tagline")}</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Language toggle */}
        <button
          onClick={() => setLanguage(language === "ar" ? "en" : "ar")}
          className="text-xs border border-white/20 rounded-lg px-2.5 py-1.5
                     text-slate-300 hover:text-white hover:border-white/40 transition"
        >
          {language === "ar" ? "EN" : "AR"}
        </button>

        {/* User badge */}
        <div className="flex items-center gap-2 border border-white/10 rounded-xl px-3 py-1.5">
          <div className="w-6 h-6 rounded-full bg-blue-700 flex items-center justify-center text-xs font-bold select-none">
            {initial}
          </div>
          <span className="text-sm text-slate-300 hidden sm:inline">{displayName}</span>
        </div>

        {/* Logout */}
        <button
          onClick={logout}
          title={t("auth.logout")}
          className="text-xs text-slate-400 hover:text-white transition px-2 py-1.5"
        >
          ⏻
        </button>
      </div>
    </header>
  );
}
