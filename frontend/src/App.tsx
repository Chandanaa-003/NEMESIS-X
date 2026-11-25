import { MotionConfig } from 'motion/react'
import { useEffect } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { DashboardLayout } from './components/dashboard/DashboardLayout'
import { AuthProvider } from './context/AuthContext'
import { DashboardPage } from './pages/DashboardPage'
import { DashboardSectionPage } from './pages/DashboardSectionPage'
import { EventTimelinePage } from './pages/EventTimelinePage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NewAnalysisPage } from './pages/NewAnalysisPage'
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
      <AuthProvider>
        <BrowserRouter>
          <ScrollManager />
          <Routes>
            {/* Public & Auth routes */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>

            {/* Protected Dashboard & Analysis workspace routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path="/analysis/new" element={<NewAnalysisPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route
                  path="/dashboard/new-analysis"
                  element={<Navigate to="/analysis/new" replace />}
                />
                <Route
                  path="/dashboard/live"
                  element={
                    <DashboardSectionPage
                      title="Live Monitoring"
                      routePath="/dashboard/live"
                      iconKey="live"
                      badgeText="COMING SOON"
                      description="Coming Soon — Real-time webcam and camera stream monitoring with instant English & Kannada alerts will be available in an upcoming development stage."
                    />
                  }
                />
                <Route path="/dashboard/timeline" element={<EventTimelinePage />} />
                <Route
                  path="/dashboard/evidence"
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
                  path="/dashboard/history"
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
                  path="/dashboard/settings"
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
            </Route>

            {/* Fallback 404 */}
            <Route element={<PublicLayout />}>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </MotionConfig>
  )
}

export default App
