//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

interface UserProfile {
  id: string
  name: string
  email: string
  permissions?: string[]
}

interface UserState {
  user: UserProfile | null
  token: string | null
  isAuthenticated: boolean
  setUser: (user: UserProfile | null) => void
  setToken: (token: string | null) => void
  clearAuth: () => void
}

/**
 * User Store - Manages authenticated user state and JWT token
 * Persisted to localStorage for session continuity
 */
export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      clearAuth: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    {
      name: "vyasa-user-store",
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

