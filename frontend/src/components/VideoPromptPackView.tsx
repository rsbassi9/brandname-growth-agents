import { CheckCircle2, Clipboard, Video } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

interface ProviderPrompt {
  role: string;
  prompt: string;
  settings?: Record<string, unknown>;
}

interface VideoPromptPack {
  kind: "video_prompt_pack";
  title: string;
  hook: string;
  shot_list: Array<{ time: string; shot: string; motion: string }>;
  on_screen_text: string[];
  providers: Record<string, ProviderPrompt>;
  manual_use?: string;
}

const preferredProviders = ["muapi.ai", "fal.ai", "Runway", "Kling"];

export function parseVideoPromptPack(value: string): VideoPromptPack | null {
  try {
    const parsed = JSON.parse(value) as Partial<VideoPromptPack>;
    if (parsed.kind !== "video_prompt_pack" || !parsed.providers || !parsed.shot_list) {
      return null;
    }
    return parsed as VideoPromptPack;
  } catch {
    return null;
  }
}

export function VideoPromptPackView({ content, compact = false }: { content: string; compact?: boolean }) {
  const pack = useMemo(() => parseVideoPromptPack(content), [content]);
  const providerNames = useMemo(
    () => (pack ? preferredProviders.filter((name) => pack.providers[name]).concat(Object.keys(pack.providers).filter((name) => !preferredProviders.includes(name))) : []),
    [pack],
  );
  const [activeProvider, setActiveProvider] = useState(providerNames[0] || "");
  const [copiedProvider, setCopiedProvider] = useState("");

  if (!pack) {
    return null;
  }

  const selectedProvider = pack.providers[activeProvider] || pack.providers[providerNames[0]];

  async function copyPrompt() {
    if (!selectedProvider?.prompt) return;
    await navigator.clipboard?.writeText(selectedProvider.prompt);
    setCopiedProvider(activeProvider);
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border bg-surface p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Video className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <h3 className="text-base font-semibold">{pack.title}</h3>
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{pack.hook}</p>
          </div>
          <Badge tone="ink">manual paste</Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {pack.on_screen_text.map((label) => (
            <Badge key={label} tone="neutral">
              {label}
            </Badge>
          ))}
        </div>
      </div>

      {!compact ? (
        <div className="grid gap-2 md:grid-cols-5">
          {pack.shot_list.map((shot) => (
            <div key={shot.time} className="rounded-md border border-border bg-background p-3">
              <p className="font-mono text-xs text-muted-foreground">{shot.time}</p>
              <p className="mt-2 text-sm font-medium">{shot.shot}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{shot.motion}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="rounded-md border border-border bg-background p-3">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Video prompt providers">
          {providerNames.map((name) => {
            const selected = name === activeProvider || (!activeProvider && name === providerNames[0]);
            return (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={selected}
                className={cn(
                  "min-h-11 rounded-md border px-3 text-sm font-medium transition-colors duration-ui ease-ui focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  selected ? "border-accent bg-accent-soft text-accent-soft-foreground" : "border-border bg-surface hover:bg-muted",
                )}
                onClick={() => setActiveProvider(name)}
              >
                {name}
              </button>
            );
          })}
        </div>

        {selectedProvider ? (
          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Badge tone={selectedProvider.role === "primary" ? "success" : "neutral"}>{selectedProvider.role}</Badge>
              <Button type="button" variant="outline" size="sm" onClick={copyPrompt}>
                {copiedProvider === activeProvider ? <CheckCircle2 className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
                {copiedProvider === activeProvider ? "Copied" : "Copy prompt"}
              </Button>
            </div>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-surface p-3 font-sans text-sm leading-6">
              {selectedProvider.prompt}
            </pre>
            {selectedProvider.settings ? (
              <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                {Object.entries(selectedProvider.settings).map(([key, value]) => (
                  <div key={key} className="rounded-md border border-border bg-surface p-2">
                    <dt className="font-medium text-foreground">{key.replace(/_/g, " ")}</dt>
                    <dd className="mt-1 font-mono">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
