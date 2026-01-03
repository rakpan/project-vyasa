//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import Image from "next/image"
import { cn } from "@/lib/utils"

interface ProjectLogoProps {
  className?: string
  align?: "left" | "center"
}

/**
 * Project Vyasa Logo Component - Secure-by-Design Layout Pattern
 * Uses Next.js Image component with fill property to prevent layout shifts
 * Automatically optimizes JPEG for bandwidth efficiency
 */
export function ProjectLogo({ className, align = "left" }: ProjectLogoProps) {
  return (
    <div className={cn("relative h-8 w-full px-2 overflow-hidden", className)}>
      <Image
        src="/vyasa_logo.jpeg"
        alt="Project Vyasa Logo"
        fill
        priority
        className={cn(
          "object-contain",
          align === "left" ? "object-left" : "object-center"
        )}
      />
    </div>
  )
}

