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
import { promises as fs } from "fs"
import { join } from "path"
import yaml from "js-yaml"

// Path resolution: In Next.js standalone mode, we need to resolve relative to project root
// process.cwd() should point to the project root when running
const FORBIDDEN_VOCAB_PATH = join(process.cwd(), "deploy", "forbidden_vocab.yaml")

/**
 * GET /api/settings/vocab-guard
 * Retrieve forbidden vocabulary configuration
 */
export async function GET(request: NextRequest) {
  try {
    // Read the YAML file
    const fileContents = await fs.readFile(FORBIDDEN_VOCAB_PATH, "utf-8")
    const data = yaml.load(fileContents) as any

    // Normalize the data format for frontend
    const forbiddenWords = data?.forbidden_words || []
    const normalizedWords = Array.isArray(forbiddenWords)
      ? forbiddenWords.map((item: any) => {
          if (typeof item === "string") {
            return { word: item, alternative: "" }
          }
          if (typeof item === "object" && item !== null) {
            // Handle both string and array alternatives
            const alternative = item.alternative
            const alternativeStr = Array.isArray(alternative)
              ? alternative.join(" or ")
              : (alternative || "")
            
            return {
              word: item.word || "",
              alternative: alternativeStr,
            }
          }
          return { word: "", alternative: "" }
        })
      : []

    return NextResponse.json({
      forbidden_words: normalizedWords.filter((w: any) => w.word),
    })
  } catch (error: any) {
    // If file doesn't exist, return empty list
    if (error.code === "ENOENT") {
      return NextResponse.json({
        forbidden_words: [],
      })
    }

    console.error("Failed to load forbidden vocabulary:", error)
    return NextResponse.json(
      { error: "Failed to load vocabulary guard settings" },
      { status: 500 }
    )
  }
}

/**
 * POST /api/settings/vocab-guard
 * Update forbidden vocabulary configuration
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

    // Convert to YAML format
    // If alternative contains " or ", split it back into an array for YAML
    const yamlData = {
      forbidden_words: normalizedWords.map((item: any) => {
        const alternative = item.alternative || ""
        // If alternative contains " or ", split it into an array
        const alternativeArray = alternative.includes(" or ")
          ? alternative.split(" or ").map((a: string) => a.trim()).filter((a: string) => a)
          : (alternative ? [alternative] : [])
        
        return {
          word: item.word,
          alternative: alternativeArray.length > 1 ? alternativeArray : (alternativeArray[0] || ""),
        }
      }),
    }

    // Write to file
    const yamlString = yaml.dump(yamlData, {
      lineWidth: 120,
      quotingType: '"',
      forceQuotes: false,
    })

    // Ensure the directory exists
    const dir = join(process.cwd(), "deploy")
    await fs.mkdir(dir, { recursive: true })

    await fs.writeFile(FORBIDDEN_VOCAB_PATH, yamlString, "utf-8")

    return NextResponse.json({
      success: true,
      message: "Vocabulary guard settings updated successfully",
    })
  } catch (error: any) {
    console.error("Failed to save forbidden vocabulary:", error)
    return NextResponse.json(
      { error: error.message || "Failed to save vocabulary guard settings" },
      { status: 500 }
    )
  }
}

