import { useState } from 'react'

export interface DetectionOverlaySettings {
  annotatedView: boolean
  showLabels: boolean
  showConfidence: boolean
  showTrackIds: boolean
  showBoundingBoxes: boolean
  labelMode: 'compact' | 'detailed'
}

const STORAGE_KEY = 'nemesis_x_detection_overlay_v1'

export const DEFAULT_DETECTION_OVERLAY_SETTINGS: DetectionOverlaySettings = {
  annotatedView: true,
  showLabels: true,
  showConfidence: true,
  showTrackIds: true,
  showBoundingBoxes: true,
  labelMode: 'detailed',
}

export function useDetectionOverlaySettings() {
  const [settings, setSettings] = useState<DetectionOverlaySettings>(() => {
    if (typeof window === 'undefined') return DEFAULT_DETECTION_OVERLAY_SETTINGS
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      return stored
        ? { ...DEFAULT_DETECTION_OVERLAY_SETTINGS, ...JSON.parse(stored) }
        : DEFAULT_DETECTION_OVERLAY_SETTINGS
    } catch {
      return DEFAULT_DETECTION_OVERLAY_SETTINGS
    }
  })

  const updateSettings = (patch: Partial<DetectionOverlaySettings>) => {
    setSettings((current) => {
      const next = { ...current, ...patch }
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        // The current view remains configurable even if browser storage is unavailable.
      }
      return next
    })
  }

  return { settings, updateSettings }
}
