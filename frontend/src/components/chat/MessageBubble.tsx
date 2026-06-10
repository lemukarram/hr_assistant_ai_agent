import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export interface Source {
  section: string;
  page: number;
  score: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  sources?: Source[];
  streaming?: boolean;
  error?: boolean;
}

interface Props {
  message: Message;
}

export default function MessageBubble({ message: msg }: Props) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-lg bg-blue-700 flex items-center justify-center text-sm shrink-0 me-2 mt-1 select-none">
          🤖
        </div>
      )}

      <div className={`max-w-[80%] flex flex-col gap-1`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-ee-sm"
              : msg.error
              ? "bg-red-900/40 border border-red-500/30 text-red-300 rounded-es-sm"
              : "bg-slate-800 text-slate-100 rounded-es-sm"
          }`}
        >
          {isUser ? (
            <span>{msg.content}</span>
          ) : (
            <>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                className="prose prose-invert prose-sm max-w-none
                           prose-p:my-1 prose-ul:my-1 prose-li:my-0.5
                           prose-table:text-xs"
              >
                {msg.content}
              </ReactMarkdown>
              {msg.streaming && (
                <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ms-1 rounded-sm align-middle" />
              )}
            </>
          )}
        </div>

        {/* RAG citations */}
        {!isUser && msg.sources && msg.sources.length > 0 && !msg.streaming && (
          <div className="flex flex-wrap gap-1 px-1">
            {msg.sources.map((src, i) => (
              <span
                key={i}
                className="text-xs text-slate-500 bg-slate-800/60 border border-white/5 rounded-md px-2 py-0.5"
              >
                📄 {src.section}، ص{src.page}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
