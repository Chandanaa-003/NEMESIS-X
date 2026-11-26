import {
  Clock,
  Brain,
  BriefcaseBusiness,
  History,
  LayoutDashboard,
  LogOut,
  MapPinned,
  Radio,
  ScanSearch,
  Settings,
  ShieldCheck,
  TrendingUp,
  UploadCloud,
  UsersRound,
  X,
} from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/useAuth'
import { BrandLogo } from '../BrandLogo'

interface SidebarNavItem {
  label: string
  to: string
  end?: boolean
  icon: typeof LayoutDashboard
}

const DASHBOARD_NAV_ITEMS: SidebarNavItem[] = [
  { label: 'Dashboard', to: '/dashboard', end: true, icon: LayoutDashboard },
  { label: 'New Analysis', to: '/analysis/new', icon: UploadCloud },
  { label: 'Live Monitoring', to: '/dashboard/live', icon: Radio },
  { label: 'Event Timeline', to: '/dashboard/timeline', icon: Clock },
  { label: 'Evidence Center', to: '/dashboard/evidence', icon: ShieldCheck },
  { label: 'Behaviour Intelligence', to: '/dashboard/behaviour', icon: Brain },
  { label: 'Smart Zones', to: '/dashboard/zones', icon: MapPinned },
  { label: 'Investigation Workspace', to: '/dashboard/investigations', icon: BriefcaseBusiness },
  { label: 'Intelligent Video Search', to: '/dashboard/search', icon: ScanSearch },
  { label: 'Unique Entities', to: '/dashboard/identities', icon: UsersRound },
  { label: 'Monitoring History', to: '/dashboard/history', icon: History },
  { label: 'Intelligence Analytics', to: '/dashboard/analytics', icon: TrendingUp },
  { label: 'Settings', to: '/dashboard/settings', icon: Settings },
]

interface SidebarProps {
  mobileOpen: boolean
  onCloseMobile: () => void
}

function getUserInitials(name?: string): string {
  if (!name) return 'NX'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'NX'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    onNavigate?.()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full flex-col justify-between bg-white">
      <div>
        {/* Brand header */}
        <div className="flex h-16 items-center justify-between border-b border-slate-200/80 px-5">
          <Link to="/" onClick={onNavigate} aria-label="NEMESIS-X Landing Page">
            <BrandLogo />
          </Link>
          {onNavigate && (
            <button
              type="button"
              onClick={onNavigate}
              aria-label="Close navigation sidebar"
              className="rounded-lg p-1.5 text-[#64748B] hover:bg-[#F5F8FC] hover:text-[#111827] lg:hidden"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Workspace tag */}
        <div className="px-4 pt-5 pb-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-[#F5F8FC] px-2.5 py-1 font-mono text-[10px] font-semibold tracking-wider text-[#64748B] uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-[#2563EB]" />
            Intelligence Workspace
          </span>
        </div>

        {/* Navigation links */}
        <nav className="space-y-1 px-3 py-2" aria-label="Dashboard navigation">
          {DASHBOARD_NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `group flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${
                    isActive
                      ? 'border border-[#2563EB]/20 bg-[#EFF6FF] font-semibold text-[#2563EB] shadow-2xs'
                      : 'border border-transparent text-[#64748B] hover:bg-[#F5F8FC] hover:text-[#111827]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-4.5 w-4.5 shrink-0 transition-colors ${
                        isActive
                          ? 'text-[#2563EB]'
                          : 'text-[#64748B] group-hover:text-[#111827]'
                      }`}
                    />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* Bottom user profile section */}
      <div className="border-t border-slate-200/80 p-3.5">
        <div className="flex items-center justify-between gap-2 rounded-2xl border border-slate-200/90 bg-[#F5F8FC] p-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#2563EB] to-[#7C3AED] font-display text-xs font-bold text-white">
              {getUserInitials(user?.full_name)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-[#111827]">
                {user?.full_name || 'Authenticated User'}
              </p>
              <p className="truncate font-mono text-[10px] text-[#64748B]">
                {user?.email || 'Active Session'}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
            className="cursor-pointer rounded-lg p-1.5 text-[#64748B] transition-colors hover:bg-white hover:text-rose-600"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

export function Sidebar({ mobileOpen, onCloseMobile }: SidebarProps) {
  return (
    <>
      {/* Desktop persistent sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-slate-200/80 bg-white lg:sticky lg:top-0 lg:block lg:h-screen">
        <SidebarContent />
      </aside>

      {/* Mobile responsive slide-over sidebar */}
      <AnimatePresence>
        {mobileOpen && (
          <div className="fixed inset-0 z-50 flex lg:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={onCloseMobile}
              aria-hidden="true"
              className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs"
            />
            <motion.aside
              initial={{ x: -272 }}
              animate={{ x: 0 }}
              exit={{ x: -272 }}
              transition={{ duration: 0.24, ease: 'easeOut' }}
              className="relative z-10 h-full w-68 max-w-[82vw] border-r border-slate-200 bg-white shadow-2xl"
            >
              <SidebarContent onNavigate={onCloseMobile} />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
