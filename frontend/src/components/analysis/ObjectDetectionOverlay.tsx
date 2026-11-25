import type { DetectionOverlaySettings } from './detectionOverlaySettings'

export interface OverlayDetection {
  class_name: string
  confidence: number
  bbox: { x1: number; y1: number; x2: number; y2: number }
  track_id?: number | null
  track_code?: string | null
  identity_code?: string | null
}

interface LabelPlacement {
  detection: OverlayDetection
  index: number
  x: number
  y: number
  width: number
  height: number
  fontSize: number
  mainText: string
  confidenceText: string
  color: string
}

function classLabel(name: string): string {
  return name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function objectColor(className: string): string {
  const name = className.toLowerCase()
  if (name === 'person') return '#2563EB'
  if (['bicycle', 'bus', 'car', 'motorcycle', 'train', 'truck'].includes(name)) return '#B45309'
  return '#7C3AED'
}

function rectanglesOverlap(
  left: Pick<LabelPlacement, 'x' | 'y' | 'width' | 'height'>,
  right: Pick<LabelPlacement, 'x' | 'y' | 'width' | 'height'>,
): boolean {
  return (
    left.x < right.x + right.width &&
    left.x + left.width > right.x &&
    left.y < right.y + right.height &&
    left.y + left.height > right.y
  )
}

function placeLabels(
  detections: OverlayDetection[],
  width: number,
  height: number,
  settings: DetectionOverlaySettings,
): LabelPlacement[] {
  if (!settings.annotatedView || !settings.showLabels || width <= 0 || height <= 0) return []

  const fontSize = Math.max(11, Math.min(24, width * (settings.labelMode === 'compact' ? 0.018 : 0.016)))
  const horizontalPadding = Math.max(5, fontSize * 0.45)
  const verticalPadding = Math.max(3, fontSize * 0.3)
  const gap = Math.max(3, fontSize * 0.25)
  const maxLabelWidth = Math.max(fontSize * 7, width * 0.72)
  const candidates = detections
    .map((detection, index) => {
      const classText = classLabel(detection.class_name)
      const trackText =
        settings.showTrackIds && detection.track_id !== null && detection.track_id !== undefined
          ? detection.identity_code || detection.track_code || ''
          : ''
      const confidenceText = [
        settings.showTrackIds && detection.identity_code && detection.track_code
          ? `Track ${detection.track_code}`
          : '',
        settings.showConfidence ? `${Math.round(detection.confidence * 100)}% confidence` : '',
      ].filter(Boolean).join(' · ')
      const compactConfidence = settings.showConfidence
        ? `${Math.round(detection.confidence * 100)}%`
        : ''
      const mainText = [
        classText,
        trackText,
        settings.labelMode === 'compact' ? compactConfidence : '',
      ].filter(Boolean).join(' · ')
      const lineCount = settings.labelMode === 'detailed' && confidenceText ? 2 : 1
      const textWidth = Math.max(mainText.length, confidenceText.length) * fontSize * 0.58
      const labelWidth = Math.min(maxLabelWidth, textWidth + horizontalPadding * 2)
      const labelHeight = lineCount * fontSize * 1.15 + verticalPadding * 2
      const box = detection.bbox
      return {
        detection,
        index,
        labelWidth,
        labelHeight,
        fontSize,
        mainText,
        confidenceText: lineCount === 2 ? confidenceText : '',
        color: objectColor(detection.class_name),
        boxX: Math.max(0, Math.min(width, box.x1)),
        boxY: Math.max(0, Math.min(height, box.y1)),
        boxBottom: Math.max(0, Math.min(height, box.y2)),
        boxArea: Math.max(0, box.x2 - box.x1) * Math.max(0, box.y2 - box.y1),
      }
    })
    .sort((left, right) => right.boxArea - left.boxArea || left.index - right.index)

  const placed: LabelPlacement[] = []
  for (const candidate of candidates) {
    const labelWidth = Math.min(candidate.labelWidth, width)
    const labelHeight = Math.min(candidate.labelHeight, height)
    const x = Math.max(0, Math.min(width - labelWidth, candidate.boxX))
    const above = candidate.boxY - labelHeight - gap
    const below = candidate.boxBottom + gap
    const proposedYs = [above, below]
    for (let step = 1; step <= 8; step += 1) {
      proposedYs.push(above - step * (labelHeight + gap), below + step * (labelHeight + gap))
    }
    const validYs = proposedYs
      .filter((y) => y >= 0 && y + labelHeight <= height)
      .map((y) => ({ x, y, width: labelWidth, height: labelHeight }))
    const position =
      validYs.find((next) => !placed.some((previous) => rectanglesOverlap(previous, next))) ??
      validYs[0] ??
      { x, y: Math.max(0, Math.min(height - labelHeight, candidate.boxY)), width: labelWidth, height: labelHeight }
    placed.push({
      detection: candidate.detection,
      index: candidate.index,
      ...position,
      fontSize: candidate.fontSize,
      mainText: candidate.mainText,
      confidenceText: candidate.confidenceText,
      color: candidate.color,
    })
  }
  return placed.sort((left, right) => left.index - right.index)
}

export function ObjectDetectionOverlay({
  detections,
  width,
  height,
  settings,
  className = '',
}: {
  detections: OverlayDetection[]
  width: number
  height: number
  settings: DetectionOverlaySettings
  className?: string
}) {
  if (!settings.annotatedView || width <= 0 || height <= 0) return null
  const labels = placeLabels(detections, width, height, settings)

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      className={`pointer-events-none absolute inset-0 h-full w-full ${className}`}
      aria-label="Detected object labels and bounding boxes"
    >
      {settings.showBoundingBoxes && detections.map((detection, index) => {
        const x1 = Math.max(0, Math.min(width - 1, detection.bbox.x1))
        const y1 = Math.max(0, Math.min(height - 1, detection.bbox.y1))
        const x2 = Math.max(x1 + 1, Math.min(width, detection.bbox.x2))
        const y2 = Math.max(y1 + 1, Math.min(height, detection.bbox.y2))
        const color = objectColor(detection.class_name)
        const strokeWidth = Math.max(1.5, Math.min(width, height) * 0.003)
        return (
          <rect
            key={`box-${detection.track_id ?? 'untracked'}-${index}`}
            data-object-class={detection.class_name}
            x={x1}
            y={y1}
            width={x2 - x1}
            height={y2 - y1}
            rx={Math.max(1, strokeWidth)}
            fill={color}
            fillOpacity={0.08}
            stroke={color}
            strokeWidth={strokeWidth}
          />
        )
      })}
      {labels.map((label) => {
        const padding = Math.max(5, label.fontSize * 0.45)
        const mainY = label.y + padding + label.fontSize
        const mainWidth = Math.max(1, label.width - padding * 2)
        return (
          <g key={`label-${label.detection.track_id ?? 'untracked'}-${label.index}`}>
            <rect
              x={label.x}
              y={label.y}
              width={label.width}
              height={label.height}
              rx={Math.max(3, label.fontSize * 0.28)}
              fill={label.color}
              fillOpacity={0.96}
              stroke="#FFFFFF"
              strokeOpacity={0.9}
              strokeWidth={Math.max(1, label.fontSize * 0.08)}
            />
            <text
              x={label.x + padding}
              y={mainY}
              fill="#FFFFFF"
              fontSize={label.fontSize}
              fontWeight="700"
              fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
              textLength={Math.min(label.mainText.length * label.fontSize * 0.58, mainWidth)}
              lengthAdjust="spacingAndGlyphs"
            >
              {label.mainText}
            </text>
            {label.confidenceText && (
              <text
                x={label.x + padding}
                y={mainY + label.fontSize * 1.1}
                fill="#FFFFFF"
                fillOpacity={0.92}
                fontSize={label.fontSize * 0.82}
                fontWeight="600"
                fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
                textLength={Math.min(label.confidenceText.length * label.fontSize * 0.48, mainWidth)}
                lengthAdjust="spacingAndGlyphs"
              >
                {label.confidenceText}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

export function ObjectOverlayControls({
  settings,
  onChange,
  compact = false,
}: {
  settings: DetectionOverlaySettings
  onChange: (patch: Partial<DetectionOverlaySettings>) => void
  compact?: boolean
}) {
  return (
    <div
      className={`flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2.5 text-xs text-slate-700 ${compact ? '' : 'sm:px-4'}`}
      aria-label="Object label configuration"
    >
      <label className="inline-flex items-center gap-1.5">
        <input type="checkbox" checked={settings.annotatedView} onChange={(event) => onChange({ annotatedView: event.target.checked })} />
        Annotated view
      </label>
      <label className="inline-flex items-center gap-1.5">
        <input type="checkbox" checked={settings.showBoundingBoxes} onChange={(event) => onChange({ showBoundingBoxes: event.target.checked })} />
        Bounding boxes
      </label>
      <label className="inline-flex items-center gap-1.5">
        <input type="checkbox" checked={settings.showLabels} onChange={(event) => onChange({ showLabels: event.target.checked })} />
        Labels
      </label>
      <label className="inline-flex items-center gap-1.5">
        <input type="checkbox" checked={settings.showTrackIds} onChange={(event) => onChange({ showTrackIds: event.target.checked })} />
        Tracking IDs
      </label>
      <label className="inline-flex items-center gap-1.5">
        <input type="checkbox" checked={settings.showConfidence} onChange={(event) => onChange({ showConfidence: event.target.checked })} />
        Confidence
      </label>
      <label className="inline-flex items-center gap-2">
        Label mode
        <select
          value={settings.labelMode}
          onChange={(event) => onChange({ labelMode: event.target.value as DetectionOverlaySettings['labelMode'] })}
          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
          aria-label="Label mode"
        >
          <option value="compact">Compact</option>
          <option value="detailed">Detailed</option>
        </select>
      </label>
    </div>
  )
}
