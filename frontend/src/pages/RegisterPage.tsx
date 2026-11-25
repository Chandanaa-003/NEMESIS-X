import { ArrowRight, Info, Mail, User } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AuthLayout } from '../components/auth/AuthLayout'
import { GoogleSignInButton } from '../components/auth/GoogleSignInButton'
import { PasswordInput } from '../components/auth/PasswordInput'

interface RegisterErrors {
  fullName?: string
  email?: string
  password?: string
  confirmPassword?: string
  terms?: string
}

export function RegisterPage() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [errors, setErrors] = useState<RegisterErrors>({})
  const [notice, setNotice] = useState<string | null>(null)

  const validate = (): RegisterErrors => {
    const nextErrors: RegisterErrors = {}
    const trimmedName = fullName.trim()
    const trimmedEmail = email.trim()

    if (!trimmedName) {
      nextErrors.fullName = 'Full name is required.'
    }
    if (!trimmedEmail) {
      nextErrors.email = 'Email address is required.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      nextErrors.email = 'Enter a valid email address.'
    }
    if (!password) {
      nextErrors.password = 'Password is required.'
    } else if (password.length < 8) {
      nextErrors.password = 'Use at least 8 characters for your password.'
    }
    if (!confirmPassword) {
      nextErrors.confirmPassword = 'Please confirm your password.'
    } else if (confirmPassword !== password) {
      nextErrors.confirmPassword = 'Passwords do not match.'
    }
    if (!acceptedTerms) {
      nextErrors.terms = 'Please accept the Terms and Conditions to continue.'
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
      'Registration form validated. Account creation API integration will be connected in the backend auth chunk.',
    )
  }

  const handleGoogleClick = () => {
    setNotice(
      'Google Sign-In button ready. OAuth client configuration will connect in the authentication chunk.',
    )
  }

  return (
    <AuthLayout
      heading="Create Your Account"
      subheading="Start understanding your videos with AI."
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
            htmlFor="register-name"
            className="block text-xs font-semibold tracking-wide text-[#111827]"
          >
            Full Name
          </label>
          <div className="relative mt-1.5">
            <User
              className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[#64748B]"
              aria-hidden="true"
            />
            <input
              id="register-name"
              name="fullName"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => {
                setFullName(e.target.value)
                if (errors.fullName) setErrors((prev) => ({ ...prev, fullName: undefined }))
              }}
              placeholder="Aarav Sharma"
              aria-invalid={Boolean(errors.fullName)}
              className={`w-full rounded-xl border bg-white py-2.5 pr-4 pl-10 text-sm text-[#111827] placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2 ${
                errors.fullName
                  ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500/20'
                  : 'border-slate-200 focus:border-[#2563EB] focus:ring-[#2563EB]/20'
              }`}
            />
          </div>
          {errors.fullName && (
            <p className="mt-1.5 text-xs font-medium text-rose-600">{errors.fullName}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="register-email"
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
              id="register-email"
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
          {errors.email && (
            <p className="mt-1.5 text-xs font-medium text-rose-600">{errors.email}</p>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <PasswordInput
            id="register-password"
            name="password"
            label="Password"
            value={password}
            autoComplete="new-password"
            error={errors.password}
            onChange={(val) => {
              setPassword(val)
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }))
            }}
          />

          <PasswordInput
            id="register-confirm-password"
            name="confirmPassword"
            label="Confirm Password"
            value={confirmPassword}
            autoComplete="new-password"
            error={errors.confirmPassword}
            onChange={(val) => {
              setConfirmPassword(val)
              if (errors.confirmPassword)
                setErrors((prev) => ({ ...prev, confirmPassword: undefined }))
            }}
          />
        </div>

        <div>
          <label className="inline-flex cursor-pointer items-start gap-2.5 text-xs leading-relaxed text-[#64748B]">
            <input
              type="checkbox"
              checked={acceptedTerms}
              onChange={(e) => {
                setAcceptedTerms(e.target.checked)
                if (errors.terms) setErrors((prev) => ({ ...prev, terms: undefined }))
              }}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#2563EB] focus:ring-[#2563EB]/30"
            />
            <span>
              I agree to the{' '}
              <span className="font-semibold text-[#111827]">Terms and Conditions</span> and{' '}
              <span className="font-semibold text-[#111827]">Privacy Policy</span>.
            </span>
          </label>
          {errors.terms && <p className="mt-1.5 text-xs font-medium text-rose-600">{errors.terms}</p>}
        </div>

        <button
          type="submit"
          className="mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#7C3AED] px-5 py-3 text-sm font-semibold text-white shadow-md shadow-[#2563EB]/20 transition-all hover:opacity-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2563EB]/40"
        >
          <span>Create Account</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-[#64748B]">
        Already have an account?{' '}
        <Link
          to="/login"
          className="font-semibold text-[#2563EB] transition-colors hover:text-[#1D4ED8]"
        >
          Sign In
        </Link>
      </p>
    </AuthLayout>
  )
}
