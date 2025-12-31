"use client"

import { useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

type Thought = {
  id: string
  sentence: string
  expert: "Lead Counsel" | "Logician" | "Synthesizer"
  bubble: string
}

interface LiveTraceProps {
  thoughts?: Thought[]
  onReprocess?: (mode: "DETAIL" | "SUMMARY") => void
}

const defaultThoughts: Thought[] = [
  {
    id: "lc-1",
    sentence: "This section repeats prior thesis material.",
    expert: "Lead Counsel",
    bubble: "Strategic Choice: Detailed (Foundational Proof)",
  },
  {
    id: "log-1",
    sentence: "Equation aligns with linear trend.",
    expert: "Logician",
    bubble: "Formalizing: $y = mx + b$",
  },
  {
    id: "syn-1",
    sentence: "Use evidence from page 3 to support the claim.",
    expert: "Synthesizer",
    bubble: "Building Case: Integrating Evidence...",
  },
]

const expertColor: Record<Thought["expert"], string> = {
  "Lead Counsel": "border-amber-400/60 bg-amber-400/10",
  Logician: "border-sky-400/60 bg-sky-400/10",
  Synthesizer: "border-emerald-400/60 bg-emerald-400/10",
}

export function LiveTrace({ thoughts, onReprocess }: LiveTraceProps) {
  const items = useMemo(() => thoughts || defaultThoughts, [thoughts])

  return (
    <Card className="w-72 bg-card/80 border-border/60 flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50">
        <div className="text-sm font-semibold">Live Trace</div>
        <div className="flex gap-2">
          <Button variant="outline" size="xs" onClick={() => onReprocess?.("DETAIL")}>
            Strategic Reprocess
          </Button>
        </div>
      </div>
      <ScrollArea className="h-[70vh] px-3 py-2">
        <div className="relative flex flex-col gap-4">
          <div className="absolute left-2 top-0 bottom-0 w-px bg-border/60" aria-hidden />
          {items.map((t) => (
            <div key={t.id} className="relative pl-6">
              <div className="absolute left-0 top-2 h-3 w-3 rounded-full bg-primary shadow" />
              <div className={cn("rounded-xl border p-3 text-sm shadow-sm", expertColor[t.expert])}>
                <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">{t.expert}</div>
                <div className="font-medium mb-1">{t.bubble}</div>
                <div className="text-xs text-muted-foreground">{t.sentence}</div>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="px-3 py-2 border-t border-border/50 text-xs text-muted-foreground">
        Follows PDF scroll; shows per-sentence expert reasoning.
      </div>
    </Card>
  )
}
