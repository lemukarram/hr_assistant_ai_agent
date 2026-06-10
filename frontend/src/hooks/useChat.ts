import { useState, useRef, useCallback } from "react";
import { createSSEStream } from "../utils/api";
import { useLanguageStore } from "../store/language";
import type { Message } from "../components/chat/MessageBubble";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const { language } = useLanguageStore();

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim() || sending) return;
      setSending(true);

      const userMsg: Message = {
        id: `u-${Date.now()}`,
        role: "user",
        content: text.trim(),
      };
      const assistantId = `a-${Date.now() + 1}`;
      const assistantMsg: Message = {
        id: assistantId,
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
              m.id === assistantId ? { ...m, content: m.content + token } : m
            )
          );
        },
        () => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, streaming: false } : m
            )
          );
          setSending(false);
        },
        (err) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, streaming: false, error: true, content: "حدث خطأ. يرجى المحاولة مرة أخرى." }
                : m
            )
          );
          setSending(false);
          console.error(err);
        }
      );
    },
    [sending, language]
  );

  const cancelStream = useCallback(() => {
    abortRef.current?.abort();
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m))
    );
    setSending(false);
  }, []);

  const clearMessages = useCallback(() => {
    cancelStream();
    setMessages([]);
  }, [cancelStream]);

  return { messages, sending, sendMessage, cancelStream, clearMessages };
}
