interface Props {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZE = { sm: "w-4 h-4", md: "w-6 h-6", lg: "w-8 h-8" };

export default function Spinner({ size = "md", className = "" }: Props) {
  return (
    <span
      role="status"
      aria-label="loading"
      className={`inline-block rounded-full border-2 border-current border-t-transparent animate-spin ${SIZE[size]} ${className}`}
    />
  );
}
