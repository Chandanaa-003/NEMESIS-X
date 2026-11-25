import { MotionConfig } from 'motion/react'
import { useEffect } from 'react'
import { BrowserRouter, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { DashboardLayout } from './components/dashboard/DashboardLayout'
import { DashboardPage } from './pages/DashboardPage'
import { DashboardSectionPage } from './pages/DashboardSectionPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RegisterPage } from './pages/RegisterPage'

function ScrollManager() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) {
      const target = document.getElementById(hash.slice(1))
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' })
        return
      }
    }
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [pathname, hash])

  return null
}

function PublicLayout() {
  return (
    <div className="min-h-screen bg-white text-[#111827]">
      <Navbar />
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export function App() {
  return (
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <ScrollManager />
        <Routes>
          {/* Public & Auth routes */}
          <Route element={<PublicLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          {/* Dashboard workspace routes */}
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<DashboardPage />} />
            <Route
              path="new-analysis"
              element={
                <DashboardSectionPage
                  title="New Analysis"
                  routePath="/dashboard/new-analysis"
                  iconKey="upload"
                  description="Video upload and analysis configuration workspace placeholder. Backend ingestion and AI pipeline endpoints will connect here in an upcoming chunk."
                />
              }
            />
            <Route
              path="live"
              element={
                <DashboardSectionPage
                  title="Live Monitoring"
                  routePath="/dashboard/live"
                  iconKey="live"
                  description="Real-time stream monitoring and bilingual alert workspace placeholder. Live camera feeds and WebSocket alerts will connect in a later chunk."
                />
              }
            />
            <Route
              path="timeline"
              element={
                <DashboardSectionPage
                  title="Event Timeline"
                  routePath="/dashboard/timeline"
                  iconKey="timeline"
                  description="Chronological event discovery timeline placeholder. Temporal event markers and multi-object tracks will populate here once connected to the backend."
                />
              }
            />
            <Route
              path="evidence"
              element={
                <DashboardSectionPage
                  title="Evidence Center"
                  routePath="/dashboard/evidence"
                  iconKey="evidence"
                  description="Timestamped visual evidence and incident report center placeholder. Annotated keyframes and evidence clips from storage/evidence will appear here."
                />
              }
            />
            <Route
              path="history"
              element={
                <DashboardSectionPage
                  title="Analysis History"
                  routePath="/dashboard/history"
                  iconKey="history"
                  description="Completed video analysis archive placeholder. Historical runs, durations, and downloadable reports will be managed here."
                />
              }
            />
            <Route
              path="settings"
              element={
                <DashboardSectionPage
                  title="Settings"
                  routePath="/dashboard/settings"
                  iconKey="settings"
                  description="Workspace preferences placeholder for alert language settings (English & Kannada), thresholds, and account configuration."
                />
              }
            />
          </Route>

          {/* Fallback 404 */}
          <Route element={<PublicLayout />}>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </MotionConfig>
  )
}

export default App
