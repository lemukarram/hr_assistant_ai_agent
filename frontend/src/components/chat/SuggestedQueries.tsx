interface Props {
  queries: string[];
  onSelect: (q: string) => void;
}

export default function SuggestedQueries({ queries, onSelect }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {queries.map((q) => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="text-start bg-white/5 hover:bg-white/10
                     border border-white/10 hover:border-blue-500/50
                     rounded-xl p-3 text-sm text-slate-300 hover:text-white
                     transition"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
