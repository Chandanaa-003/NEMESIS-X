import { ArrowRight, PlayCircle, Radio, Sparkles } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

/*
 * Hero video asset location:
 * Place an MP4 loop at `frontend/public/videos/hero-loop.mp4` (served at `/videos/hero-loop.mp4`).
 * When absent, the animated CSS + SVG computer-vision fallback renders automatically.
 */
const HERO_VIDEO_PATH = '/videos/hero-loop.mp4'

export function HeroSection() {
  const prefersReducedMotion = useReducedMotion()
  const [videoReady, setVideoReady] = useState(false)
  const [videoMissing, setVideoMissing] = useState(false)

  const showVideo = videoReady && !videoMissing

  return (
    <section className="relative overflow-hidden bg-white pt-14 pb-20 sm:pt-20 sm:pb-28">
      {/* Subtle blue & violet gradient lighting */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="animate-gradient-drift absolute -top-32 left-1/4 h-96 w-96 rounded-full bg-[#2563EB]/10 blur-3xl" />
        <div className="animate-gradient-drift absolute top-12 right-1/6 h-80 w-80 rounded-full bg-[#7C3AED]/10 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-12 lg:gap-10 lg:px-8">
        {/* Left column: Copy & CTAs */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: 'easeOut' }}
          className="lg:col-span-6"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-[#F5F8FC] px-3.5 py-1.5 text-xs font-semibold tracking-wide text-[#2563EB]">
            <Sparkles className="h-3.5 w-3.5 text-[#7C3AED]" />
            <span>Beyond Detection. Into Understanding.</span>
          </div>

          <h1 className="mt-6 font-display text-4xl leading-[1.1] font-extrabold tracking-tight text-[#111827] sm:text-5xl lg:text-[3.5rem]">
            Your Videos Have Stories.{' '}
            <span className="bg-gradient-to-r from-[#2563EB] to-[#7C3AED] bg-clip-text text-transparent">
              Discover Them.
            </span>
          </h1>

          <p className="mt-5 max-w-xl text-base leading-relaxed text-[#64748B] sm:text-lg">
            NEMESIS-X transforms raw surveillance and operational footage into structured intelligence.
            Combine multi-object tracking, temporal memory, and contextual reasoning to pinpoint
            meaningful events with timestamped visual evidence.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-[#2563EB] px-6 py-3.5 text-sm font-semibold text-white shadow-md shadow-[#2563EB]/20 transition-all hover:-translate-y-0.5 hover:bg-[#1D4ED8] hover:shadow-lg hover:shadow-[#2563EB]/25"
            >
              <span>Start Analyzing</span>
              <ArrowRight className="h-4 w-4" />
            </Link>

            <a
              href="#features"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3.5 text-sm font-semibold text-[#111827] shadow-xs transition-all hover:border-slate-300 hover:bg-[#F5F8FC]"
            >
              <PlayCircle className="h-4 w-4 text-[#2563EB]" />
              <span>Explore Features</span>
            </a>
          </div>

          {/* Subtle capability trust strip */}
          <div className="mt-10 grid grid-cols-3 gap-4 border-t border-slate-200/80 pt-6">
            <div>
              <p className="text-xs font-medium tracking-wide text-[#64748B] uppercase">Detection</p>
              <p className="mt-1 text-sm font-semibold text-[#111827]">Multi-Object IDs</p>
            </div>
            <div>
              <p className="text-xs font-medium tracking-wide text-[#64748B] uppercase">Context</p>
              <p className="mt-1 text-sm font-semibold text-[#111827]">Temporal Memory</p>
            </div>
            <div>
              <p className="text-xs font-medium tracking-wide text-[#64748B] uppercase">Evidence</p>
              <p className="mt-1 text-sm font-semibold text-[#111827]">Exact Timestamps</p>
            </div>
          </div>
        </motion.div>

        {/* Right column: Cinematic AI Video Visual with fallback */}
        <motion.div
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1, ease: 'easeOut' }}
          className="relative lg:col-span-6"
        >
          {/* Floating ambient card glow */}
          <div
            aria-hidden="true"
            className="absolute -inset-3 rounded-3xl bg-gradient-to-tr from-[#2563EB]/15 via-transparent to-[#7C3AED]/15 blur-xl"
          />

          <div className="relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-xl shadow-slate-200/60">
            {/* Top telemetry bar */}
            <div className="flex items-center justify-between border-b border-slate-200/80 bg-[#F5F8FC] px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#2563EB]" />
                <span className="font-mono text-xs font-medium text-[#111827]">
                  NEMESIS-X // VISION STREAM
                </span>
              </div>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 font-mono text-[11px] font-medium text-[#64748B]">
                <Radio className="h-3 w-3 text-[#7C3AED]" />
                {showVideo ? 'VIDEO LOOP' : 'CV SIMULATION'}
              </span>
            </div>

            {/* Video / Animated CV Fallback viewport */}
            <div className="relative aspect-[16/10] w-full overflow-hidden bg-[#F5F8FC]">
              {/* Real HTML video element (renders cleanly when /videos/hero-loop.mp4 is provided) */}
              {!videoMissing && (
                <video
                  src={HERO_VIDEO_PATH}
                  autoPlay
                  muted
                  loop
                  playsInline
                  onCanPlay={() => setVideoReady(true)}
                  onError={() => setVideoMissing(true)}
                  className={`h-full w-full object-cover transition-opacity duration-500 ${
                    showVideo ? 'opacity-100' : 'opacity-0'
                  }`}
                />
              )}

              {/* Light readability scrim when real video is active */}
              {showVideo && (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 bg-gradient-to-t from-white/75 via-white/10 to-white/40"
                />
              )}

              {/* Animated CSS + SVG computer-vision fallback when MP4 is missing */}
              {!showVideo && (
                <div className="bg-cv-grid absolute inset-0 overflow-hidden bg-gradient-to-br from-[#F5F8FC] via-white to-[#EEF2FF]">
                  {/* Subtle geometric scene layout (corridor / entryway schematic) */}
                  <svg
                    viewBox="0 0 640 400"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-full w-full"
                    aria-hidden="true"
                  >
                    {/* Architectural perspective floor & zone markers */}
                    <path d="M80 370L210 215H430L560 370" stroke="#CBD5E1" strokeWidth="1.5" />
                    <path d="M210 215V80H430V215" stroke="#CBD5E1" strokeWidth="1.5" />
                    <rect
                      x="255"
                      y="245"
                      width="130"
                      height="68"
                      rx="6"
                      fill="#2563EB"
                      fillOpacity="0.06"
                      stroke="#2563EB"
                      strokeOpacity="0.3"
                      strokeDasharray="5 5"
                    />
                    <text
                      x="275"
                      y="283"
                      fill="#2563EB"
                      fontSize="11"
                      fontFamily="JetBrains Mono, monospace"
                      fontWeight="600"
                    >
                      ZONE A · MONITORED
                    </text>

                    {/* Motion trajectory arc */}
                    <path
                      d="M150 280C215 245 275 240 345 260C400 276 455 250 495 225"
                      stroke="#7C3AED"
                      strokeOpacity="0.4"
                      strokeWidth="2"
                      strokeDasharray="6 6"
                    />
                    <circle cx="150" cy="280" r="4" fill="#2563EB" />
                    <circle cx="345" cy="260" r="4" fill="#7C3AED" />
                    <circle cx="495" cy="225" r="4" fill="#7C3AED" />
                  </svg>

                  {/* Animated vertical scan beam */}
                  {!prefersReducedMotion && (
                    <div
                      aria-hidden="true"
                      className="animate-cv-scan pointer-events-none absolute inset-x-0 top-0 h-14 bg-gradient-to-b from-transparent via-[#2563EB]/15 to-transparent"
                    />
                  )}
                </div>
              )}

              {/* Animated detection boxes, tracking IDs & timestamp overlays (always visible & legible) */}
              <div className="pointer-events-none absolute inset-0 p-4">
                {/* Top-left timestamp & FPS readout */}
                <div className="flex items-center justify-between">
                  <div className="rounded-lg border border-slate-200/90 bg-white/90 px-2.5 py-1 font-mono text-[11px] font-semibold text-[#111827] shadow-xs backdrop-blur-sm">
                    00:14:22.08 <span className="text-[#64748B]">| 30 FPS</span>
                  </div>
                  <div className="rounded-lg border border-[#7C3AED]/25 bg-white/90 px-2.5 py-1 font-mono text-[11px] font-semibold text-[#7C3AED] shadow-xs backdrop-blur-sm">
                    TEMPORAL WINDOW: ACTIVE
                  </div>
                </div>

                {/* Animated Tracking Box 1: Person */}
                <motion.div
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={
                    prefersReducedMotion
                      ? { opacity: 1, scale: 1 }
                      : {
                          opacity: 1,
                          scale: 1,
                          x: [0, 14, 6, 0],
                          y: [0, -6, 4, 0],
                        }
                  }
                  transition={
                    prefersReducedMotion
                      ? { duration: 0.3 }
                      : {
                          opacity: { duration: 0.4, delay: 0.2 },
                          x: { duration: 7, repeat: Infinity, ease: 'easeInOut' },
                          y: { duration: 7, repeat: Infinity, ease: 'easeInOut' },
                        }
                  }
                  className="absolute top-[28%] left-[18%] h-[34%] w-[22%] rounded-lg border-2 border-[#2563EB] bg-[#2563EB]/5 shadow-sm"
                >
                  <div className="absolute -top-6 left-0 inline-flex items-center gap-1.5 rounded-md bg-[#2563EB] px-2 py-0.5 font-mono text-[10px] font-semibold whitespace-nowrap text-white shadow-xs">
                    <span>ID #04</span>
                    <span className="opacity-80">Person · 98%</span>
                  </div>
                </motion.div>

                {/* Animated Tracking Box 2: Object / Contextual Target */}
                <motion.div
                  initial={{ opacity: 0, scale: 0.94 }}
                  animate={
                    prefersReducedMotion
                      ? { opacity: 1, scale: 1 }
                      : {
                          opacity: 1,
                          scale: 1,
                          x: [0, -12, -4, 0],
                          y: [0, 6, -4, 0],
                        }
                  }
                  transition={
                    prefersReducedMotion
                      ? { duration: 0.3 }
                      : {
                          opacity: { duration: 0.4, delay: 0.35 },
                          x: { duration: 8.5, repeat: Infinity, ease: 'easeInOut' },
                          y: { duration: 8.5, repeat: Infinity, ease: 'easeInOut' },
                        }
                  }
                  className="absolute top-[42%] right-[16%] h-[28%] w-[26%] rounded-lg border-2 border-[#7C3AED] bg-[#7C3AED]/5 shadow-sm"
                >
                  <div className="absolute -top-6 right-0 inline-flex items-center gap-1.5 rounded-md bg-[#7C3AED] px-2 py-0.5 font-mono text-[10px] font-semibold whitespace-nowrap text-white shadow-xs">
                    <span>ID #11</span>
                    <span className="opacity-80">Asset · 96%</span>
                  </div>
                </motion.div>

                {/* Bottom contextual understanding bar */}
                <div className="absolute inset-x-4 bottom-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/90 bg-white/92 px-3.5 py-2.5 shadow-sm backdrop-blur-md">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
                    <span className="text-xs font-semibold text-[#111827]">
                      Contextual Cue: Zone A entry sequence tracked
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-[#64748B]">
                    {showVideo ? 'Live Loop' : 'Fallback CV View · Add /videos/hero-loop.mp4'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
