import { AlertCircle, CheckCircle2, FileDown, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { downloadAnalysisPdfReport } from '../../services/analysisService'
import { getAuthErrorMessage } from '../../services/authService'

interface PdfDownloadButtonProps {
  analysisId: string
  disabled?: boolean
}

export function PdfDownloadButton({ analysisId, disabled = false }: PdfDownloadButtonProps) {
  const [isDownloading, setIsDownloading] = useState(false)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleDownload = async () => {
    if (!analysisId || isDownloading || disabled) return
    setIsDownloading(true)
    setStatusMsg(null)
    setErrorMsg(null)

    try {
      await downloadAnalysisPdfReport(analysisId)
      setStatusMsg(`Report nemesis-x-report-${analysisId.slice(0, 8)}.pdf downloaded.`)
    } catch (error) {
      setErrorMsg(getAuthErrorMessage(error, 'Failed to generate or download PDF report.'))
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <button
        type="button"
        onClick={handleDownload}
        disabled={disabled || isDownloading}
        className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[#2563EB]/25 bg-[#EFF6FF] px-4 py-2.5 text-xs font-semibold text-[#2563EB] transition-colors hover:bg-[#2563EB] hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isDownloading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Generating PDF...</span>
          </>
        ) : (
          <>
            <FileDown className="h-4 w-4" />
            <span>Download PDF Report</span>
          </>
        )}
      </button>

      {statusMsg && (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {statusMsg}
        </span>
      )}

      {errorMsg && (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600">
          <AlertCircle className="h-3.5 w-3.5" />
          {errorMsg}
        </span>
      )}
    </div>
  )
}
