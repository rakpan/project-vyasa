import { NextRequest, NextResponse } from "next/server"

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || "http://orchestrator:8000"

export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get("content-type") || ""
    if (!contentType.includes("multipart/form-data")) {
      return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 })
    }

    const formData = await request.formData()
    const file = formData.get("file")

    if (!file || !(file instanceof File)) {
      return NextResponse.json({ error: "Missing file" }, { status: 400 })
    }

    // Forward the file to orchestrator for PDF processing
    const forwardForm = new FormData()
    forwardForm.append("file", file, file.name)

    const response = await fetch(`${ORCHESTRATOR_URL}/ingest/pdf`, {
      method: "POST",
      body: forwardForm,
    })

    const data = await response.json()

    if (!response.ok) {
      return NextResponse.json(
        { error: data?.error || "PDF processing failed", status: response.status },
        { status: response.status },
      )
    }

    return NextResponse.json({
      markdown: data.markdown,
      images: data.images || [],
      filename: data.filename || file.name,
    })
  } catch (error) {
    console.error("PDF upload failed:", error)
    return NextResponse.json(
      { error: "Failed to upload PDF for processing" },
      { status: 500 },
    )
  }
}
