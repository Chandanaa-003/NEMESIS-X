import { Eye, EyeOff, Lock } from 'lucide-react'
import { useState } from 'react'

interface PasswordInputProps {
  id: string
  name: string
  label: string
  value: string
  placeholder?: string
  autoComplete?: string
  error?: string
  onChange: (value: string) => void
}

export function PasswordInput({
  id,
  name,
  label,
  value,
  placeholder = '••••••••',
  autoComplete,
  error,
  onChange,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold tracking-wide text-[#111827]">
        {label}
      </label>
      <div className="relative mt-1.5">
        <Lock
          className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-[#64748B]"
          aria-hidden="true"
        />
        <input
          id={id}
          name={name}
          type={visible ? 'text' : 'password'}
          value={value}
          autoComplete={autoComplete}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={Boolean(error)}
          className={`w-full rounded-xl border bg-white py-2.5 pr-11 pl-10 text-sm text-[#111827] placeholder:text-slate-400 transition-colors focus:outline-none focus:ring-2 ${
            error
              ? 'border-rose-300 focus:border-rose-500 focus:ring-rose-500/20'
              : 'border-slate-200 focus:border-[#2563EB] focus:ring-[#2563EB]/20'
          }`}
        />
        <button
          type="button"
          onClick={() => setVisible((prev) => !prev)}
          aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute top-1/2 right-2.5 inline-flex h-7 w-7 -translate-y-1/2 cursor-pointer items-center justify-center rounded-lg text-[#64748B] transition-colors hover:bg-[#F5F8FC] hover:text-[#111827]"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error && <p className="mt-1.5 text-xs font-medium text-rose-600">{error}</p>}
    </div>
  )
}
