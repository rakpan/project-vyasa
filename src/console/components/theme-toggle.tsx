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

import { Moon, Sun } from "lucide-react"
import { useTheme } from "./theme-provider"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  // Force light theme (as per design system)
  const isLight = true

  return (
    <button
      className="h-8 w-8 rounded-md flex items-center justify-center text-[#111827] hover:bg-slate-100 transition-colors"
      onClick={() => setTheme("light")}
      aria-label="Theme (light mode only)"
      disabled
    >
      <Sun className="h-3.5 w-3.5" />
    </button>
  )
}

