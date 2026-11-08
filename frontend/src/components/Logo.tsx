import { cn } from '@/lib/utils'

/** The Delphi mark: a peach delta (Δ, for Delphi) on dark green. Decorative: the name sits next to it. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn('size-8 shrink-0', className)}>
      <rect width="32" height="32" rx="8" className="fill-forest" />
      <path
        d="M16 7 25 24H7Z"
        fill="none"
        className="stroke-peach"
        strokeWidth="3"
        strokeLinejoin="round"
      />
    </svg>
  )
}
