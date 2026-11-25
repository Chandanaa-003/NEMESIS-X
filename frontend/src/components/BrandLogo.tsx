interface BrandLogoProps {
  compact?: boolean
}

export function BrandLogo({ compact = false }: BrandLogoProps) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <svg
        width="32"
        height="32"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <defs>
          <linearGradient id="nemesis-logo-grad" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="100%" stopColor="#7C3AED" />
          </linearGradient>
        </defs>
        <rect x="1.5" y="1.5" width="29" height="29" rx="8" fill="url(#nemesis-logo-grad)" />
        {/* Precision detection corners */}
        <path
          d="M8.5 11.5V9.5C8.5 8.94772 8.94772 8.5 9.5 8.5H11.5M20.5 8.5H22.5C23.0523 8.5 23.5 8.94772 23.5 9.5V11.5M23.5 20.5V22.5C23.5 23.0523 23.0523 23.5 22.5 23.5H20.5M11.5 23.5H9.5C8.94772 23.5 8.5 23.0523 8.5 22.5V20.5"
          stroke="white"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
        {/* Central optical intelligence node */}
        <circle cx="16" cy="16" r="3.25" stroke="white" strokeWidth="1.75" />
        <circle cx="16" cy="16" r="1.25" fill="white" />
      </svg>

      {!compact && (
        <span className="flex items-center gap-1.5">
          <span className="font-display text-lg font-bold tracking-tight text-[#111827]">
            NEMESIS<span className="bg-gradient-to-r from-[#2563EB] to-[#7C3AED] bg-clip-text text-transparent">-X</span>
          </span>
        </span>
      )}
    </span>
  )
}
