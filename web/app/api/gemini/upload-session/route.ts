import { NextRequest, NextResponse } from "next/server"
import { createClient } from "@/utils/supabase/server"

const GEMINI_UPLOAD_ENDPOINT = "https://generativelanguage.googleapis.com/upload/v1beta/files"
const MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024

export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey) {
      return NextResponse.json({ error: "Missing GEMINI_API_KEY" }, { status: 500 })
    }

    const body = await request.json()
    const { fileName, mimeType, sizeBytes } = body as {
      fileName?: string
      mimeType?: string
      sizeBytes?: number
    }

    if (!fileName || !mimeType || !sizeBytes) {
      return NextResponse.json({ error: "fileName, mimeType, sizeBytes are required" }, { status: 400 })
    }

    if (mimeType !== "application/pdf") {
      return NextResponse.json({ error: "Only PDF upload sessions are supported" }, { status: 400 })
    }

    if (sizeBytes > MAX_PDF_SIZE_BYTES) {
      return NextResponse.json({ error: `PDF too large. Max ${MAX_PDF_SIZE_BYTES} bytes` }, { status: 400 })
    }

    const sanitizedFileName = fileName.replace(/[\r\n]/g, " ").slice(0, 120)

    const startResponse = await fetch(`${GEMINI_UPLOAD_ENDPOINT}?key=${apiKey}`, {
      method: "POST",
      headers: {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": String(sizeBytes),
        "X-Goog-Upload-Header-Content-Type": mimeType,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        file: {
          display_name: sanitizedFileName,
        },
      }),
    })

    if (!startResponse.ok) {
      const errText = await startResponse.text()
      return NextResponse.json({ error: `Failed to start Gemini upload session: ${errText}` }, { status: 502 })
    }

    const uploadUrl = startResponse.headers.get("x-goog-upload-url")
    if (!uploadUrl) {
      return NextResponse.json({ error: "Gemini upload URL not found in response headers" }, { status: 502 })
    }

    return NextResponse.json({ uploadUrl })
  } catch (error: any) {
    return NextResponse.json({ error: error?.message || "Unexpected error" }, { status: 500 })
  }
}
