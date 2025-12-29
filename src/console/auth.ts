//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const consolePassword = process.env.CONSOLE_PASSWORD;
        
        if (!consolePassword) {
          console.error("CONSOLE_PASSWORD environment variable is not set");
          return null;
        }

        if (credentials?.password === consolePassword) {
          return {
            id: "1",
            name: "Project Vyasa User",
            email: "user@project-vyasa.local",
          };
        }

        return null;
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  secret: process.env.NEXTAUTH_SECRET,
})

