import { cn } from '@/lib/utils'

/**
 * The Delphi mark: the Delphic epsilon. An "E" was carved at Apollo's temple at Delphi, next to
 * "Know thyself". Square ends make it read like an inscription. Decorative: the name sits next to it.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn('size-8 shrink-0', className)}>
      <rect width="32" height="32" rx="8" className="fill-forest" />
      <path
        d="M11.5 9H21.5M11.5 16H19M11.5 23H21.5M11.5 9V23"
        fill="none"
        className="stroke-peach"
        strokeWidth="3"
        strokeLinecap="square"
      />
    </svg>
  )
}

/**
 * A Greek key (meander) border: the one ornamental touch, under the header.
 * Pure decoration, so it's hidden from screen readers.
 */
export function GreekKey({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={cn('block h-5 w-full', className)}>
      <defs>
        {/* One key per 20px: a line along the bottom, and a square spiral rising from it */}
        <pattern id="greek-key" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M0 17H20M15 17V3H4V12H10V8" fill="none" stroke="currentColor" strokeWidth="2" />
        </pattern>
      </defs>
      <rect width="100%" height="20" fill="url(#greek-key)" />
    </svg>
  )
}
