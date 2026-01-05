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
import { NextRequest, NextResponse } from "next/server"

/**
 * GET /api/settings/vocab-guard
 * Retrieve forbidden vocabulary configuration from orchestrator (DB-backed)
 */
export async function GET(request: NextRequest) {
  try {
    // Proxy to orchestrator API
    // Use Docker service name for internal communication
    const orchestratorUrl = process.env.ORCHESTRATOR_SERVICE_URL || "http://orchestrator:8000"
    const response = await fetch(`${orchestratorUrl}/api/settings/vocab-guard`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`Orchestrator API error: ${response.status} ${errorText}`)
      return NextResponse.json(
        { error: "Failed to load vocabulary guard settings" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error("Failed to load forbidden vocabulary:", error)
    return NextResponse.json(
      { error: "Failed to load vocabulary guard settings" },
      { status: 500 }
    )
  }
}

/**
 * POST /api/settings/vocab-guard
 * Update forbidden vocabulary configuration (proxies to orchestrator, DB-backed)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { forbidden_words } = body

    if (!Array.isArray(forbidden_words)) {
      return NextResponse.json(
        { error: "forbidden_words must be an array" },
        { status: 400 }
      )
    }

    // Normalize and validate the data
    const normalizedWords = forbidden_words
      .map((item: any) => {
        if (typeof item === "string") {
          return { word: item.trim(), alternative: "" }
        }
        if (typeof item === "object" && item !== null) {
          return {
            word: (item.word || "").trim(),
            alternative: (item.alternative || "").trim(),
          }
        }
        return null
      })
      .filter((item: any) => item && item.word) // Remove empty/null entries

    // Proxy to orchestrator API
    // Use Docker service name for internal communication
    const orchestratorUrl = process.env.ORCHESTRATOR_SERVICE_URL || "http://orchestrator:8000"
    const response = await fetch(`${orchestratorUrl}/api/settings/vocab-guard`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        forbidden_words: normalizedWords,
      }),
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error(`Orchestrator API error: ${response.status} ${errorText}`)
      return NextResponse.json(
        { error: "Failed to save vocabulary guard settings" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error: any) {
    console.error("Failed to save forbidden vocabulary:", error)
    return NextResponse.json(
      { error: error.message || "Failed to save vocabulary guard settings" },
      { status: 500 }
    )
  }
}

