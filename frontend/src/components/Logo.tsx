import { cn } from '@/lib/utils'

/**
 * The Delphi symbol: two arcs turned toward each other, ")(", with a staff through the middle
 * and a bar across. Drawn in a 32x32 box centred on (16, 16).
 */
function Symbol({ strokeWidth = 2 }: { strokeWidth?: number }) {
  return (
    <g fill="none" className="stroke-peach" strokeWidth={strokeWidth} strokeLinecap="round">
      <path d="M10.5 9Q14 16 10.5 23" />
      <path d="M21.5 9Q18 16 21.5 23" />
      <path d="M16 9.5V22.5" />
      <path d="M9.5 16H22.5" />
    </g>
  )
}

/** The logo at small sizes (header, favicon): the symbol in a dark green medallion with a double ring. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cn('size-8 shrink-0', className)}>
      <circle cx="16" cy="16" r="15.25" className="fill-forest stroke-peach" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="12.75" fill="none" className="stroke-peach/50" strokeWidth="0.75" />
      <Symbol />
    </svg>
  )
}

// One Greek key, drawn at the top of the ring between radius 80 and 96 (in a 200x200 box
// centred on 0, 0). Repeating it rotated around the circle makes the meander ring.
const KEYS = 24
const KEY = 'M-11.5 -82H6V-94H-6V-86H1V-90'

/** The large medallion with a full Greek-key ring, for places with room for the detail. */
export function Medallion({ className }: { className?: string }) {
  return (
    <svg viewBox="-100 -100 200 200" aria-hidden="true" className={cn('shrink-0', className)}>
      <g fill="none" className="stroke-peach" strokeWidth="2.5">
        <circle r="97" />
        <circle r="79" />
        {Array.from({ length: KEYS }, (_, i) => (
          <path key={i} d={KEY} transform={`rotate(${(360 / KEYS) * i})`} />
        ))}
      </g>
      {/* The symbol, scaled up from its 32px box to fill the inner circle */}
      <g transform="translate(-72 -72) scale(4.5)">
        <Symbol strokeWidth={1.2} />
      </g>
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
