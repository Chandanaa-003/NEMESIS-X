import { Home, LayoutDashboard, LogIn, Shield, UserPlus } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Home', icon: Home },
  { to: '/login', label: 'Login', icon: LogIn },
  { to: '/register', label: 'Register', icon: UserPlus },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
]

export function Navbar() {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
        <NavLink to="/" className="flex items-center gap-2 font-semibold text-white">
          <Shield className="h-5 w-5 text-cyan-400" />
          <span>NEMESIS-X</span>
        </NavLink>

        <nav className="flex items-center gap-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-cyan-500/20 text-cyan-300'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  )
}
