//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { SessionProvider as NextAuthSessionProvider } from "next-auth/react"
import type { ReactNode } from "react"

interface SessionProviderProps {
  children: ReactNode
}

/**
 * SessionProvider Wrapper for NextAuth
 * Provides session context to all child components
 */
export function SessionProvider({ children }: SessionProviderProps) {
  return <NextAuthSessionProvider>{children}</NextAuthSessionProvider>
}

