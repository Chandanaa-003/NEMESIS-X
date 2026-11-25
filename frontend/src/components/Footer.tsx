import { Link } from 'react-router-dom'
import { BrandLogo } from './BrandLogo'

export function Footer() {
  return (
    <footer className="border-t border-slate-200/80 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-6 px-4 py-10 sm:flex-row sm:items-center sm:px-6 lg:px-8">
        <div>
          <BrandLogo />
          <p className="mt-2 text-sm text-[#64748B]">Beyond Detection. Into Understanding.</p>
        </div>

        <div className="flex flex-wrap items-center gap-6 text-sm text-[#64748B]">
          <a href="#intelligence-preview" className="transition-colors hover:text-[#111827]">
            Product
          </a>
          <a href="#features" className="transition-colors hover:text-[#111827]">
            Features
          </a>
          <a href="#how-it-works" className="transition-colors hover:text-[#111827]">
            How It Works
          </a>
          <Link to="/login" className="transition-colors hover:text-[#111827]">
            Login
          </Link>
          <Link to="/dashboard" className="transition-colors hover:text-[#111827]">
            Dashboard
          </Link>
        </div>
      </div>
    </footer>
  )
}
