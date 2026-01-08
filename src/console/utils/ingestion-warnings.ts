export interface IngestionWarning {
  code: string
  severity?: string
  message?: string
}

export interface IngestionTriage {
  likely_scanned?: boolean
  preview_text_chars?: number
  pages_previewed?: number
}

const DEFAULT_VISION_MESSAGE =
  "This PDF looks scanned or image-heavy. Vision is OFF, so OCR/figure extraction may be limited."

export function getVisionOffScannedWarning(
  warnings?: IngestionWarning[] | null,
  triage?: IngestionTriage | null
) {
  const visionWarning = warnings?.find((warning) => warning.code === "VISION_OFF_SCANNED_PDF")
  if (!visionWarning || !triage?.likely_scanned) {
    return { shouldWarn: false, message: "" }
  }

  return {
    shouldWarn: true,
    message: visionWarning.message || DEFAULT_VISION_MESSAGE,
  }
}
