import React, { useState, useRef, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "../store/auth";
import { useLanguageStore } from "../store/language";
import { createSSEStream } from "../utils/api";
import ReactMarkdown from "react-markdown";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  sources?: { title: string; chunk: string; score: number }[];
  streaming?: boolean;
  error?: boolean;
}

const SUGGESTED: Record<string, string[]> = {
  ar: [
    "كم يوم إجازة سنوية تبقى لدي؟",
    "أريد الاطلاع على آخر ثلاث رواتب",
    "كم ساعة عمل إضافي لديّ هذا الشهر؟",
    "أظهر لي سجل حضوري هذا الشهر",
    "ما هي سياسة الإجازة المرضية؟",
    "أريد تقديم طلب إجازة",
    "سجّل ساعتين عمل إضافي ليوم أمس",
    "ما مزايا التأمين الصحي؟",
  ],
  en: [
    "How many annual leave days do I have left?",
    "Show me my last 3 payslips",
    "How many overtime hours do I have this month?",
    "Show me my attendance record this month",
    "What is the sick leave policy?",
    "I want to submit a leave request",
    "Log 2 overtime hours for yesterday",
    "What are my health insurance benefits?",
  ],
};

export default function ChatPage() {
  const { t } = useTranslation();
  const { employee, logout } = useAuthStore();
  const { language, setLanguage } = useLanguageStore();

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || sending) return;
      setInput("");
      setSending(true);

      const userMsg: Message = {
        id: Date.now().toString(),
        role: "user",
        content: text.trim(),
      };
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      abortRef.current = createSSEStream(
        "/chat/stream",
        { message: text.trim(), language },
        (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id ? { ...m, content: m.content + token } : m
            )
          );
        },
        () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id ? { ...m, streaming: false } : m
            )
          );
          setSending(false);
        },
        (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, streaming: false, error: true, content: t("chat.streamError") }
                : m
            )
          );
          setSending(false);
          console.error(err);
        }
      );
    },
    [sending, language, t]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-slate-900/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center text-lg">🤖</div>
          <div>
            <h1 className="font-bold text-base leading-tight">{t("chat.title")}</h1>
            <p className="text-xs text-slate-400">{t("chat.subtitle")}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setLanguage(language === "ar" ? "en" : "ar")}
            className="text-xs border border-white/20 rounded-lg px-2.5 py-1.5 text-slate-300 hover:text-white hover:border-white/40 transition"
          >
            {language === "ar" ? "EN" : "AR"}
          </button>

          <div className="flex items-center gap-2 border border-white/10 rounded-xl px-3 py-1.5">
            <div className="w-6 h-6 rounded-full bg-blue-700 flex items-center justify-center text-xs font-bold">
              {(language === "ar" ? employee?.name_ar : employee?.name_en)?.charAt(0)}
            </div>
            <span className="text-sm text-slate-300 hidden sm:inline">
              {language === "ar" ? employee?.name_ar : employee?.name_en}
            </span>
          </div>

          <button
            onClick={logout}
            className="text-xs text-slate-400 hover:text-white transition px-2 py-1.5"
            title={t("chat.logout")}
          >
            ⏻
          </button>
        </div>
      </header>

      {/* Messages */}
      <main className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <div className="text-4xl mb-3">👋</div>
              <h2 className="text-xl font-semibold text-white mb-1">
                {t("chat.welcome", {
                  name: language === "ar" ? employee?.name_ar : employee?.name_en,
                })}
              </h2>
              <p className="text-slate-400 text-sm">{t("chat.welcomeSub")}</p>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {(SUGGESTED[language] || SUGGESTED.ar).map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  className="text-start bg-white/5 hover:bg-white/10 border border-white/10 hover:border-blue-500/50 rounded-xl p-3 text-sm text-slate-300 hover:text-white transition"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} max-w-3xl mx-auto w-full`}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-lg bg-blue-700 flex items-center justify-center text-sm shrink-0 me-2 mt-1">
                🤖
              </div>
            )}
            <div
              className={`rounded-2xl px-4 py-3 max-w-[80%] text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-ee-sm"
                  : msg.error
                  ? "bg-red-900/40 border border-red-500/30 text-red-300 rounded-es-sm"
                  : "bg-slate-800 text-slate-100 rounded-es-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <>
                  <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
                    {msg.content}
                  </ReactMarkdown>
                  {msg.streaming && (
                    <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ms-1 rounded-sm" />
                  )}
                </>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      {/* Input bar */}
      <div className="shrink-0 border-t border-white/10 bg-slate-900/80 backdrop-blur px-4 py-3">
        <div className="max-w-3xl mx-auto flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("chat.placeholder")}
            rows={1}
            className="flex-1 resize-none bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm leading-relaxed max-h-32 overflow-y-auto"
            style={{ fieldSizing: "content" } as React.CSSProperties}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={sending || !input.trim()}
            className="w-11 h-11 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition shadow-lg"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
              <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>
        <p className="text-center text-slate-600 text-xs mt-2">{t("chat.disclaimer")}</p>
      </div>
    </div>
  );
}
