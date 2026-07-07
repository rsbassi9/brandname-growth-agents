import { Wand2 } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { PageHeader, Panel } from "@/components/ui/Panel";

export function PlaygroundPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Generate"
        title="Playground"
        actions={
          <Button type="button">
            <Wand2 className="h-4 w-4" />
            Generate
          </Button>
        }
      />
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(320px,420px)_1fr]">
        <Panel className="space-y-4">
          <div>
            <label className="text-sm font-medium" htmlFor="brief">
              Brief
            </label>
            <textarea
              id="brief"
              className="mt-2 min-h-40 w-full rounded-md border border-input bg-background px-3 py-3 text-sm outline-none transition focus:ring-2 focus:ring-ring"
              placeholder="Write the asset brief..."
            />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Type
              <select className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option>Copy</option>
                <option>Image Concept</option>
                <option>Carousel</option>
                <option>Video Script</option>
              </select>
            </label>
            <label className="text-sm font-medium">
              Tone
              <select className="mt-2 h-11 w-full rounded-md border border-input bg-background px-3 text-sm">
                <option>Quiet confidence</option>
                <option>Launch urgency</option>
                <option>Process proof</option>
              </select>
            </label>
          </div>
        </Panel>
        <Panel className="min-h-[420px]">
          <div className="flex h-full items-center justify-center rounded-md border border-dashed border-border bg-muted/40 p-8 text-center">
            <div>
              <p className="text-sm font-medium">Result preview</p>
              <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
                P2-2 wires this panel to `/api/v1/generate`, job events, and session history.
              </p>
            </div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
