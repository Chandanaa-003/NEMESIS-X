import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Header } from './Header'
import { Sidebar } from './Sidebar'

const ROUTE_TITLES: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/analysis/new': 'New Analysis',
  '/dashboard/new-analysis': 'New Analysis',
  '/dashboard/live': 'Live Monitoring',
  '/dashboard/timeline': 'Event Timeline',
  '/dashboard/evidence': 'Evidence Center',
  '/dashboard/history': 'Analysis History',
  '/dashboard/investigations': 'Investigation Workspace',
  '/dashboard/settings': 'Settings',
}

export function DashboardLayout() {
  const { pathname } = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const pageTitle =
    pathname.startsWith('/dashboard/investigations')
      ? 'Investigation Workspace'
      : ROUTE_TITLES[pathname] ?? 'Dashboard'

  return (
    <div className="flex min-h-screen bg-[#F5F8FC] text-[#111827]">
      <Sidebar mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          title={pageTitle}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onOpenMobileMenu={() => setMobileOpen(true)}
        />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto max-w-7xl">
            <Outlet context={{ searchQuery, setSearchQuery }} />
          </div>
        </main>
      </div>
    </div>
  )
}
