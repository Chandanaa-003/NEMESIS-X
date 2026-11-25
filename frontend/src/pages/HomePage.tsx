import { Video } from 'lucide-react'

export function HomePage() {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-6">
      <div className="flex items-center gap-2 text-cyan-400">
        <Video className="h-5 w-5" />
        <span className="text-xs font-medium tracking-wider uppercase">Home Placeholder</span>
      </div>
      <h1 className="mt-2 text-2xl font-bold text-white">NEMESIS-X</h1>
      <p className="mt-2 text-sm text-slate-400">
        Minimal application shell initialized. Landing page design will be implemented in a later chunk.
      </p>
    </section>
  )
}
