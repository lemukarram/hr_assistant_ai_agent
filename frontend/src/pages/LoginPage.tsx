import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "../store/auth";
import { useLanguageStore } from "../store/language";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

export default function LoginPage() {
  const { t } = useTranslation();
  const { login } = useAuthStore();
  const { language, setLanguage } = useLanguageStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const form = new URLSearchParams();
      form.append("username", email);
      form.append("password", password);

      const res = await fetch(`${BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      });

      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || t("login.error"));
        return;
      }

      const data = await res.json();
      login(
        { access_token: data.access_token, refresh_token: data.refresh_token },
        {
          id: data.employee_id,
          name_ar: data.name_ar,
          name_en: data.name_en,
          email,
        }
      );
    } catch {
      setError(t("login.networkError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex items-center justify-center p-4">
      {/* Language toggle */}
      <button
        onClick={() => setLanguage(language === "ar" ? "en" : "ar")}
        className="absolute top-4 end-4 text-slate-300 hover:text-white text-sm border border-slate-600 rounded-lg px-3 py-1.5 transition"
      >
        {language === "ar" ? "English" : "عربي"}
      </button>

      <div className="w-full max-w-md">
        {/* Logo / brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 mb-4 shadow-xl">
            <span className="text-2xl">🤖</span>
          </div>
          <h1 className="text-3xl font-bold text-white mb-1">{t("login.title")}</h1>
          <p className="text-slate-400 text-sm">{t("login.subtitle")}</p>
        </div>

        {/* Card */}
        <div className="bg-white/5 backdrop-blur border border-white/10 rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                {t("login.email")}
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ahmed@company.sa"
                required
                className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                {t("login.password")}
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition shadow-lg shadow-blue-900/40"
            >
              {loading ? t("login.loading") : t("login.submit")}
            </button>
          </form>

          {/* Demo credentials hint */}
          <div className="mt-6 pt-5 border-t border-white/10">
            <p className="text-slate-500 text-xs text-center mb-3">{t("login.demoHint")}</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                { email: "ahmed@company.sa", name: "أحمد الشمري" },
                { email: "sara@company.sa", name: "سارة القحطاني" },
                { email: "khalid@company.sa", name: "خالد العتيبي" },
                { email: "mona@company.sa", name: "منى الزهراني" },
              ].map((u) => (
                <button
                  key={u.email}
                  onClick={() => { setEmail(u.email); setPassword("demo1234"); }}
                  className="text-start bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-3 py-2 text-slate-400 hover:text-white transition"
                >
                  <div className="font-medium">{u.name}</div>
                  <div className="text-slate-500 truncate">{u.email}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
