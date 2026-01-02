//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { AlertCircle, CheckCircle2, Info, Lightbulb, AlertTriangle } from "lucide-react"

export type ThoughtBubbleVariant = "logician" | "critic" | "synthesizer" | "info" | "warning"

export interface ThoughtBubbleProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: ThoughtBubbleVariant
  expert?: string
  anchorId?: string
  children: React.ReactNode
}

const variantStyles: Record<ThoughtBubbleVariant, { bg: string; border: string; icon: React.ComponentType<{ className?: string }>; iconColor: string }> = {
  logician: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    icon: Lightbulb,
    iconColor: "text-blue-600",
  },
  critic: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
    iconColor: "text-amber-600",
  },
  synthesizer: {
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    icon: CheckCircle2,
    iconColor: "text-emerald-600",
  },
  info: {
    bg: "bg-slate-50",
    border: "border-slate-200",
    icon: Info,
    iconColor: "text-slate-600",
  },
  warning: {
    bg: "bg-orange-50",
    border: "border-orange-200",
    icon: AlertCircle,
    iconColor: "text-orange-600",
  },
}

/**
 * ThoughtBubble - Post-it style minimal card for expert feedback
 * Anchors to specific paragraphs in the Synthesizer editor
 */
export const ThoughtBubble = React.forwardRef<HTMLDivElement, ThoughtBubbleProps>(
  ({ variant = "info", expert, anchorId, className, children, ...props }, ref) => {
    const styles = variantStyles[variant]
    const Icon = styles.icon

    return (
      <div
        ref={ref}
        id={anchorId}
        className={cn(
          "relative rounded-md border-l-4 p-3 shadow-sm",
          styles.bg,
          styles.border,
          "transition-all duration-200 ease-in-out",
          "hover:shadow-md",
          className
        )}
        {...props}
      >
        <div className="flex items-start gap-2">
          <Icon className={cn("h-4 w-4 shrink-0 mt-0.5", styles.iconColor)} />
          <div className="flex-1 min-w-0">
            {expert && (
              <div className="text-xs font-semibold text-foreground/80 mb-1 uppercase tracking-wider">
                {expert}
              </div>
            )}
            <div className="text-sm text-foreground leading-relaxed">{children}</div>
          </div>
        </div>
        {/* Post-it corner fold effect */}
        <div className="absolute top-0 right-0 w-3 h-3 bg-white/40 rounded-bl-full" />
      </div>
    )
  }
)
ThoughtBubble.displayName = "ThoughtBubble"

/**
 * Convenience components for specific expert types
 */
export const LogicianInsight = React.forwardRef<
  HTMLDivElement,
  Omit<ThoughtBubbleProps, "variant">
>((props, ref) => <ThoughtBubble ref={ref} variant="logician" expert="Logician Insight" {...props} />)
LogicianInsight.displayName = "LogicianInsight"

export const CriticWarning = React.forwardRef<
  HTMLDivElement,
  Omit<ThoughtBubbleProps, "variant">
>((props, ref) => <ThoughtBubble ref={ref} variant="critic" expert="Critic Warning" {...props} />)
CriticWarning.displayName = "CriticWarning"

export const SynthesizerNote = React.forwardRef<
  HTMLDivElement,
  Omit<ThoughtBubbleProps, "variant">
>((props, ref) => <ThoughtBubble ref={ref} variant="synthesizer" expert="Synthesizer Note" {...props} />)
SynthesizerNote.displayName = "SynthesizerNote"

