import { ArrowRight, Info, Mail } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '../components/auth/AuthLayout'
import { GoogleSignInButton } from '../components/auth/GoogleSignInButton'
import { PasswordInput } from '../components/auth/PasswordInput'

interface LoginErrors {
  email?: string
  password?: string
}

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(true)
  const [errors, setErrors] = useState<LoginErrors>({})
  const [notice, setNotice] = useState<string | null>(null)

  const validate = (): LoginErrors => {
    const nextErrors: LoginErrors = {}
    const trimmedEmail = email.trim()
    if (!trimmedEmail) {
      nextErrors.email = 'Email address is required.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      nextErrors.email = 'Enter a valid email address.'
    }
    if (!password) {
      nextErrors.password = 'Password is required.'
    }
    return nextErrors
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationErrors = validate()
    setErrors(validationErrors)

    if (Object.keys(validationErrors).length > 0) {
      setNotice(null)
      return
    }

    setNotice(
      'Sign-in UI validated. Authentication API integration will be connected in the backend auth chunk.',
    )
  }

  const handleGoogleClick = () => {
    setNotice(
      'Google Sign-In button ready. OAuth client configuration will connect in the authentication chunk.',
    )
  }

  const handleForgotPassword = () => {
    setNotice('Password recovery is a placeholder link and will be connected with email services.')
  }

  return (
    <AuthLayout
      heading="Welcome Back"
      subheading="Sign in to continue to your video intelligence workspace."
    >
      <GoogleSignInButton onClick={handleGoogleClick} />

      <div className="my-6 flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-200" />
        <span className="font-mono text-[11px] font-semibold tracking-wider text-[#64748B]">
          OR CONTINUE WITH EMAIL
        </span>
        <div className="h-px flex-1 bg-slate-200" />
      </div>

      {notice && (
        <div
          role="status"
          className="mb-5 flex items-start gap-2.5 rounded-xl border border-[#2563EB]/25 bg-[#F5F8FC] px-3.5 py-3 text-xs leading-relaxed text-[#111827]"
        >
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#2563EB]" />
          <span>{notice}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div>
          <label
            htmlFor="login-email"
            className="block text-xs font-semibold tracking-wide text-[#111827]"
          >
            Email Address
          </label>
          <div className="relative mt-1.5">
            <Mail
              className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[#64748B]"
              aria-hidden="true"
            />
            <input
              id="login-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }))
              }}
              placeholder="you@company.com"
              aria-invalid={Boolean(errors.email)}
              className={`w-full rounded-xl border bg-white py-2.5 pr-4 pl-10 text-sm text-[#111827] placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2 ${
                errors.email
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500/20'
                  : 'border-slate-200 focus:border-[#2563EB] focus:ring-[#2563EB]/20'
              }`}
            />
          </div>
          {errors.email && <p className="mt-1.5 text-xs font-medium text-rose-600">{errors.email}</p>}
        </div>

        <PasswordInput
          id="login-password"
          name="password"
          label="Password"
          value={password}
          autoComplete="current-password"
          error={errors.password}
          onChange={(val) => {
            setPassword(val)
            if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
          }}
        />

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-medium text-[#64748B]">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-[#2563EB] focus:ring-[#2563EB]/30"
            />
            <span>Remember me</span>
          </label>

          <button
            type="button"
            onClick={handleForgotPassword}
            className="cursor-pointer text-xs font-semibold text-[#2563EB] transition-colors hover:text-[#1D4ED8]"
          >
            Forgot password?
          </button>
        </div>

        <button
          type="submit"
          className="mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-[#2563EB]/20 transition-all hover:opacity-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]/40"
        >
          <span>Sign In</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[#64748B]">
        Don&apos;t have an account?{' '}
        <Link
          to="/register"
          className="font-semibold text-[#2563EB] transition-colors hover:text-[#1D4ED8]"
        >
          Create Account
        </Link>
      </p>
    </AuthLayout>
  )
}
