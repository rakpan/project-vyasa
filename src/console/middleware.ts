//
// SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
import { auth } from "./auth"
import { NextResponse } from "next/server";

export default auth((req) => {
  const { pathname } = req.nextUrl
  const isLoggedIn = !!req.auth

  // Allow access to login page and auth API routes
  if (pathname.startsWith("/login") || pathname.startsWith("/api/auth")) {
    return NextResponse.next()
  }

  // Redirect to login if not authenticated
  if (!isLoggedIn) {
    const loginUrl = new URL("/login", req.url)
    loginUrl.searchParams.set("callbackUrl", pathname)
    
    // Preserve research context parameters (threadId, jobId, projectId, pdfUrl)
    const threadId = req.nextUrl.searchParams.get("threadId")
    const jobId = req.nextUrl.searchParams.get("jobId")
    const projectId = req.nextUrl.searchParams.get("projectId")
    const pdfUrl = req.nextUrl.searchParams.get("pdfUrl")
    
    if (threadId) loginUrl.searchParams.set("threadId", threadId)
    if (jobId) loginUrl.searchParams.set("jobId", jobId)
    if (projectId) loginUrl.searchParams.set("projectId", projectId)
    if (pdfUrl) loginUrl.searchParams.set("pdfUrl", pdfUrl)
    
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}

