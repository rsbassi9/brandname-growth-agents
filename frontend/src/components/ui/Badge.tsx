import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "ink";

const tones: Record<BadgeTone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  success: "border-success/30 bg-success-soft text-success",
  warning: "border-warning/30 bg-warning-soft text-warning",
  danger: "border-danger/30 bg-danger-soft text-danger",
  ink: "border-ink bg-ink text-ink-foreground",
};

export function Badge({
  children,
  className,
  tone = "neutral",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-full border px-2.5 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
