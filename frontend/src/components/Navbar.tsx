import { ArrowRight, Menu, X } from 'lucide-react'
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from 'motion/react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { BrandLogo } from './BrandLogo'

const sectionLinks = [
  { label: 'Product', hash: '#intelligence-preview' },
  { label: 'Features', hash: '#features' },
  { label: 'How It Works', hash: '#how-it-works' },
]

export function Navbar() {
  const { scrollY } = useScroll()
  const { pathname } = useLocation()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useMotionValueEvent(scrollY, 'change', (latest) => {
    setScrolled(latest > 16)
  })

  const handleSectionClick = () => {
    setMobileOpen(false)
  }

  return (
    <motion.header
      initial={false}
      animate={{
        backgroundColor: scrolled ? 'rgba(255, 255, 255, 0.92)' : 'rgba(255, 255, 255, 0.8)',
        boxShadow: scrolled ? '0 8px 30px -12px rgba(17, 24, 39, 0.08)' : '0 0 0 0 rgba(17, 24, 39, 0)',
      }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="sticky top-0 z-50 border-b border-slate-200/80 backdrop-blur-md"
    >
      <div
        className={`mx-auto flex max-w-7xl items-center justify-between px-4 transition-all duration-200 sm:px-6 lg:px-8 ${
          scrolled ? 'h-16' : 'h-18'
        }`}
      >
        <Link to="/" onClick={() => setMobileOpen(false)} aria-label="NEMESIS-X Home">
          <BrandLogo />
        </Link>

        {/* Desktop navigation */}
        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary navigation">
          {sectionLinks.map((item) =>
            pathname === '/' ? (
              <a
                key={item.hash}
                href={item.hash}
                className="text-sm font-medium text-[#64748B] transition-colors hover:text-[#111827]"
              >
                {item.label}
              </a>
            ) : (
              <Link
                key={item.hash}
                to={`/${item.hash}`}
                className="text-sm font-medium text-[#64748B] transition-colors hover:text-[#111827]"
              >
                {item.label}
              </Link>
            ),
          )}
        </nav>

        {/* Desktop actions */}
        <div className="hidden items-center gap-3 md:flex">
          <Link
            to="/login"
            className="rounded-lg px-4 py-2 text-sm font-medium text-[#111827] transition-colors hover:bg-[#F5F8FC] hover:text-[#2563EB]"
          >
            Login
          </Link>
          <Link
            to="/register"
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#2563EB] px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-[#2563EB]/20 transition-all hover:bg-[#1D4ED8] hover:shadow-md hover:shadow-[#2563EB]/25"
          >
            <span>Get Started</span>
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        {/* Mobile menu trigger */}
        <button
          type="button"
          onClick={() => setMobileOpen((prev) => !prev)}
          className="inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-[#111827] transition-colors hover:bg-[#F5F8FC] md:hidden"
          aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden border-t border-slate-200/80 bg-white md:hidden"
          >
            <div className="space-y-2 px-4 py-4">
              {sectionLinks.map((item) =>
                pathname === '/' ? (
                  <a
                    key={item.hash}
                    href={item.hash}
                    onClick={handleSectionClick}
                    className="block rounded-lg px-3 py-2 text-sm font-medium text-[#64748B] hover:bg-[#F5F8FC] hover:text-[#111827]"
                  >
                    {item.label}
                  </a>
                ) : (
                  <Link
                    key={item.hash}
                    to={`/${item.hash}`}
                    onClick={handleSectionClick}
                    className="block rounded-lg px-3 py-2 text-sm font-medium text-[#64748B] hover:bg-[#F5F8FC] hover:text-[#111827]"
                  >
                    {item.label}
                  </Link>
                ),
              )}

              <div className="flex flex-col gap-2 border-t border-slate-200/80 pt-3">
                <Link
                  to="/login"
                  onClick={handleSectionClick}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-center text-sm font-medium text-[#111827] hover:bg-[#F5F8FC]"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  onClick={handleSectionClick}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#2563EB] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1D4ED8]"
                >
                  <span>Get Started</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  )
}
