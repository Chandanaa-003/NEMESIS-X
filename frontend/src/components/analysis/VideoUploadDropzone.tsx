import { AlertCircle, CheckCircle2, FileVideo, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react'

const MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024 // 500 MB
const ALLOWED_EXTENSIONS = ['.mp4', '.mov', '.avi'] as const
const ALLOWED_MIME_TYPES = new Set([
  'video/mp4',
  'video/quicktime',
  'video/x-msvideo',
  'video/avi',
  'video/msvideo',
])

export interface VideoUploadDropzoneProps {
  selectedFile: File | null
  onFileSelect: (file: File | null) => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(2)} MB`
}

function validateVideoFile(file: File): string | null {
  const lowerName = file.name.toLowerCase()
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
  const hasAllowedMime = file.type ? ALLOWED_MIME_TYPES.has(file.type.toLowerCase()) : false

  if (!hasAllowedExtension && !hasAllowedMime) {
    return 'Unsupported file format. Please choose an MP4, MOV, or AVI video file.'
  }

  if (file.size === 0) {
    return 'The selected file appears to be empty. Please choose a valid video.'
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File exceeds the 500 MB limit (${formatFileSize(file.size)} selected). Please upload a smaller clip.`
  }

  return null
}

export function VideoUploadDropzone({ selectedFile, onFileSelect }: VideoUploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [previewPlaybackError, setPreviewPlaybackError] = useState(false)

  const previewUrl = useMemo(
    () => (selectedFile ? URL.createObjectURL(selectedFile) : null),
    [selectedFile],
  )

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const handleCandidateFile = (file: File | undefined) => {
    if (!file) return

    const validationError = validateVideoFile(file)
    if (validationError) {
      setErrorMessage(validationError)
      setPreviewPlaybackError(false)
      onFileSelect(null)
      return
    }

    setErrorMessage(null)
    setPreviewPlaybackError(false)
    onFileSelect(file)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    handleCandidateFile(file)
    // Reset input so re-selecting the same file after removal still triggers onChange
    event.target.value = ''
  }

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(true)
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    if (!isDragging) setIsDragging(true)
  }

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
    setIsDragging(false)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    event.stopPropagation()
    setIsDragging(false)

    const droppedFiles = event.dataTransfer.files
    if (droppedFiles.length > 1) {
      setErrorMessage('Please drop one video file at a time.')
      return
    }
    handleCandidateFile(droppedFiles[0])
  }

  const handleBrowseClick = () => {
    inputRef.current?.click()
  }

  const handleRemove = () => {
    setErrorMessage(null)
    setPreviewPlaybackError(false)
    onFileSelect(null)
  }

  return (
    <div className="space-y-4">
      <input
        ref={inputRef}
        type="file"
        accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo"
        onChange={handleInputChange}
        className="sr-only"
        aria-label="Upload video file"
      />

      {!selectedFile ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`rounded-2xl border-2 border-dashed p-8 text-center transition-all sm:p-10 ${
            isDragging
              ? 'border-[#2563EB] bg-[#EFF6FF]/70 shadow-sm'
              : 'border-slate-300 bg-[#F5F8FC]/70 hover:border-[#2563EB]/60 hover:bg-[#F5F8FC]'
          }`}
        >
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-[#2563EB]/20 bg-white text-[#2563EB] shadow-xs">
            <UploadCloud className="h-7 w-7" />
          </div>

          <h3 className="mt-4 font-display text-base font-bold text-[#111827]">
            {isDragging ? 'Drop your video here' : 'Drag and drop your video'}
          </h3>
          <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-[#64748B]">
            Supports <span className="font-semibold text-[#111827]">MP4, MOV, and AVI</span> files
            up to <span className="font-semibold text-[#111827]">500 MB</span>. Files stay local
            in your browser until backend analysis is connected.
          </p>

          <div className="mt-5 flex justify-center">
            <button
              type="button"
              onClick={handleBrowseClick}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-[#2563EB] px-5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-[#2563EB]/20 transition-colors hover:bg-[#1D4ED8]"
            >
              <FileVideo className="h-4 w-4" />
              <span>Browse Files</span>
            </button>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs"
        >
          {/* File summary bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 bg-[#F5F8FC] px-4 py-3.5">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate font-mono text-xs font-semibold text-[#111827]">
                  {selectedFile.name}
                </p>
                <p className="mt-0.5 text-xs text-[#64748B]">
                  {formatFileSize(selectedFile.size)} · Ready for configuration
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleBrowseClick}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] transition-colors hover:border-[#2563EB]/40 hover:text-[#2563EB]"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Change Video</span>
              </button>
              <button
                type="button"
                onClick={handleRemove}
                className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Remove</span>
              </button>
            </div>
          </div>

          {/* Local browser video preview */}
          <div className="bg-slate-950/5 p-4">
            {previewUrl && !previewPlaybackError ? (
              <video
                src={previewUrl}
                controls
                playsInline
                onError={() => setPreviewPlaybackError(true)}
                className="mx-auto max-h-72 w-full rounded-xl border border-slate-200 bg-slate-950 object-contain"
              />
            ) : (
              <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-[#F5F8FC] px-4 py-10 text-center">
                <FileVideo className="h-8 w-8 text-[#2563EB]" />
                <p className="mt-2 text-xs font-semibold text-[#111827]">
                  Browser preview unavailable for this video codec
                </p>
                <p className="mt-1 text-xs text-[#64748B]">
                  {selectedFile.name} ({formatFileSize(selectedFile.size)}) is still validated and
                  selected.
                </p>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {errorMessage && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-700"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  )
}
