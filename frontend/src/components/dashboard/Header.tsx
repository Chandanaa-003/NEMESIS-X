import { Bell, ChevronDown, Home, LogOut, Menu, Search, Settings, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { DEMO_NOTIFICATIONS } from '../../data/dashboardDemoData'

interface HeaderProps {
  title: string
  searchQuery: string
  onSearchChange: (value: string) => void
  onOpenMobileMenu: () => void
}

function getInitials(name?: string): string {
  if (!name) return 'NX'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'NX'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

export function Header({
  title,
  searchQuery,
  onSearchChange,
  onOpenMobileMenu,
}: HeaderProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const handleLogout = () => {
    setProfileOpen(false)
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        {/* Left: Mobile menu button + Page title */}
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onOpenMobileMenu}
            aria-label="Open navigation menu"
            className="inline-flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white text-[#111827] transition-colors hover:bg-[#F5F8FC] lg:hidden"
          >
            <Menu className="h-4.5 w-4.5" />
          </button>

          <div className="flex min-w-0 items-center gap-2.5">
            <h1 className="truncate font-display text-lg font-bold tracking-tight text-[#111827] sm:text-xl">
              {title}
            </h1>
            <span className="hidden rounded-full border border-[#7C3AED]/20 bg-[#7C3AED]/8 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#7C3AED] sm:inline-flex">
              DEMO WORKSPACE
            </span>
          </div>
        </div>

        {/* Right: Search + Notifications + Profile menu */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Search field */}
          <div className="relative hidden w-56 md:block lg:w-72">
            <Search
              className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-[#64748B]"
              aria-hidden="true"
            />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Filter sample videos or events..."
              aria-label="Search sample videos or events"
              className="w-full rounded-xl border border-slate-200 bg-[#F5F8FC] py-2 pr-8 pl-9 text-xs text-[#111827] placeholder:text-slate-400 transition-colors focus:border-[#2563EB] focus:bg-white focus:ring-2 focus:ring-[#2563EB]/20 focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => onSearchChange('')}
                aria-label="Clear search"
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-[#64748B] hover:text-[#111827]"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Notification bell + sample popover */}
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setNotificationsOpen((prev) => !prev)
                setProfileOpen(false)
              }}
              aria-label="View notifications"
              aria-expanded={notificationsOpen}
              className="relative inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl border border-slate-200 bg-white text-[#64748B] transition-colors hover:bg-[#F5F8FC] hover:text-[#111827]"
            >
              <Bell className="h-4 w-4" />
              <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-[#2563EB]" />
            </button>

            <AnimatePresence>
              {notificationsOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 mt-2 w-72 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl shadow-slate-200/70"
                >
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="text-xs font-bold text-[#111827]">Notifications</span>
                    <span className="rounded bg-[#F5F8FC] px-1.5 py-0.5 font-mono text-[10px] text-[#64748B]">
                      Sample
                    </span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {DEMO_NOTIFICATIONS.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-xl border border-slate-100 bg-[#F5F8FC] p-2.5"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-[#111827]">{item.title}</p>
                          <span className="font-mono text-[10px] text-[#64748B]">{item.time}</span>
                        </div>
                        <p className="mt-1 text-[11px] leading-relaxed text-[#64748B]">
                          {item.detail}
                        </p>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* User avatar & profile menu */}
          <div className="relative">
            <button
              type="button"
              onClick={() => {
                setProfileOpen((prev) => !prev)
                setNotificationsOpen(false)
              }}
              aria-label="Open user menu"
              aria-expanded={profileOpen}
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-white px-2 py-1.5 transition-colors hover:bg-[#F5F8FC]"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-[#2563EB] to-[#7C3AED] font-display text-[11px] font-bold text-white">
                {getInitials(user?.full_name)}
              </div>
              <span className="hidden text-xs font-semibold text-[#111827] sm:inline">
                {user?.full_name || 'Operator'}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-[#64748B]" />
            </button>

            <AnimatePresence>
              {profileOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 mt-2 w-56 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-200/70"
                >
                  <div className="border-b border-slate-100 px-3 py-2">
                    <p className="truncate text-xs font-semibold text-[#111827]">
                      {user?.full_name || 'Authenticated User'}
                    </p>
                    <p className="truncate font-mono text-[10px] text-[#64748B]">
                      {user?.email || 'Active Session'}
                    </p>
                  </div>
                  <Link
                    to="/dashboard/settings"
                    onClick={() => setProfileOpen(false)}
                    className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-[#111827] hover:bg-[#F5F8FC]"
                  >
                    <Settings className="h-3.5 w-3.5 text-[#64748B]" />
                    <span>Workspace Settings</span>
                  </Link>
                  <Link
                    to="/"
                    onClick={() => setProfileOpen(false)}
                    className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-[#111827] hover:bg-[#F5F8FC]"
                  >
                    <Home className="h-3.5 w-3.5 text-[#64748B]" />
                    <span>Landing Page</span>
                  </Link>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-left text-xs font-medium text-rose-600 hover:bg-rose-50"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>Sign Out</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </header>
  )
}
