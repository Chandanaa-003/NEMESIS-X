import { apiClient } from './api'

export type VideoStatus = 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed'

export interface VideoRecord {
  id: string
  user_id: number
  original_filename: string
  stored_filename: string
  file_path: string
  file_size: number
  mime_type: string
  duration_seconds: number | null
  width: number | null
  height: number | null
  status: VideoStatus
  created_at: string
}

export interface VideoPlaybackPreparation {
  status: 'not_started' | 'converting' | 'ready' | 'failed'
  progress: number
  message: string
}

export async function uploadVideoFile(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<VideoRecord> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post<VideoRecord>('/videos/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 0,
    onUploadProgress: (progressEvent) => {
      if (!onProgress || !progressEvent.total) return
      const percent = Math.min(
        100,
        Math.round((progressEvent.loaded * 100) / progressEvent.total),
      )
      onProgress(percent)
    },
  })

  return response.data
}

export async function listUserVideos(): Promise<VideoRecord[]> {
  const response = await apiClient.get<VideoRecord[]>('/videos')
  return response.data
}

export async function fetchVideoBlobUrl(
  videoId: string,
  onPreparationProgress?: (progress: number, message: string) => void,
): Promise<string> {
  const preparationResponse = await apiClient.post<VideoPlaybackPreparation>(
    `/videos/${videoId}/playback/prepare`,
    undefined,
    { timeout: 60000 },
  )
  let preparation = preparationResponse.data
  onPreparationProgress?.(preparation.progress, preparation.message)

  const deadline = Date.now() + 30 * 60 * 1000
  while (preparation.status === 'converting' || preparation.status === 'not_started') {
    if (Date.now() >= deadline) {
      throw new Error('Video conversion is taking too long. Annotated frame navigation remains available.')
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
    const statusResponse = await apiClient.get<VideoPlaybackPreparation>(
      `/videos/${videoId}/playback/status`,
    )
    preparation = statusResponse.data
    onPreparationProgress?.(preparation.progress, preparation.message)
  }
  if (preparation.status === 'failed') {
    throw new Error(preparation.message)
  }

  const response = await apiClient.get<Blob>(`/videos/${videoId}/playback`, {
    responseType: 'blob',
    timeout: 60000,
  })
  return URL.createObjectURL(response.data)
}
