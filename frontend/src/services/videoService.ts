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

export async function fetchVideoBlobUrl(videoId: string): Promise<string> {
  const response = await apiClient.get<Blob>(`/videos/${videoId}/stream`, {
    responseType: 'blob',
    timeout: 60000,
  })
  return URL.createObjectURL(response.data)
}
