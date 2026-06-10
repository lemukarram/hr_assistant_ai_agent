import React, { useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export default function ChatInput({ value, onChange, onSend, disabled }: Props) {
  const { t } = useTranslation();
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea
  useEffect(() => {
    if (ref.current) {
      ref.current.style.height = "auto";
      ref.current.style.height = `${Math.min(ref.current.scrollHeight, 128)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="flex items-end gap-2">
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("chat.placeholder")}
        rows={1}
        disabled={disabled}
        className="flex-1 resize-none bg-white/10 border border-white/20 rounded-xl
                   px-4 py-3 text-white placeholder-slate-500
                   focus:outline-none focus:ring-2 focus:ring-blue-500
                   text-sm leading-relaxed overflow-y-auto
                   disabled:opacity-50 disabled:cursor-not-allowed
                   transition"
      />
      <button
        onClick={onSend}
        disabled={disabled || !value.trim()}
        aria-label={t("chat.send")}
        className="w-11 h-11 rounded-xl bg-blue-600 hover:bg-blue-500
                   disabled:opacity-40 disabled:cursor-not-allowed
                   flex items-center justify-center transition shadow-lg shrink-0"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="w-5 h-5"
        >
          <path
            d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </div>
  );
}
