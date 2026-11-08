import { Link, NavLink, Outlet } from 'react-router'
import { LogoMark } from '@/components/Logo'
import { useApi, type Me } from '@/lib/api'
import { cn } from '@/lib/utils'

const links = [
  // `end` stops "/" from also counting as active on every other page
  { to: '/', label: 'Dashboard', end: true },
  { to: '/projects/new', label: 'New project', end: false },
  { to: '/portfolio', label: 'Portfolio', end: false },
  { to: '/help', label: 'Help', end: false },
]

// On the dark green header the focus ring is peach (8.5:1), since jungle green wouldn't show.
const headerFocus = 'focus-visible:ring-2 focus-visible:ring-peach focus-visible:outline-none'

/** The frame around every page: a skip link, the Delphi header with the nav, and the learner. */
export default function Layout() {
  const me = useApi<Me>('/api/me')
  const initials = me.data?.name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* Keyboard users can jump straight past the nav. Hidden until it gets focus. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-peach focus:px-3 focus:py-2 focus:font-medium focus:text-foreground"
      >
        Skip to content
      </a>

      <header className="bg-forest text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-3 sm:px-6">
          <Link to="/" className={cn('flex items-center gap-3 rounded-lg', headerFocus)}>
            <LogoMark className="size-9 [&_rect]:fill-white/10" />
            <span className="flex flex-col leading-tight">
              <span className="font-heading text-xl font-semibold tracking-tight">Delphi</span>
              <span className="text-xs text-peach">Know thy code</span>
            </span>
          </Link>

          <nav aria-label="Main" className="order-last w-full sm:order-none sm:w-auto sm:flex-1">
            <ul className="flex flex-wrap gap-1">
              {links.map((link) => (
                <li key={link.to}>
                  {/* NavLink adds aria-current="page" to the link for the page you're on */}
                  <NavLink
                    to={link.to}
                    end={link.end}
                    className={({ isActive }) =>
                      cn(
                        'block rounded-md px-3 py-2 text-sm font-medium text-white/85 hover:bg-white/10 hover:text-white',
                        headerFocus,
                        isActive && 'bg-white/10 text-white shadow-[inset_0_-2px_0_var(--peach)]',
                      )
                    }
                  >
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {me.data && (
            <p className="ml-auto flex items-center gap-2 text-sm sm:ml-0">
              <span
                aria-hidden="true"
                className="flex size-8 items-center justify-center rounded-full bg-peach text-xs font-semibold text-foreground"
              >
                {initials}
              </span>
              <span>
                {me.data.name}
                <span className="block text-xs text-white/75">@{me.data.github_login}</span>
              </span>
            </p>
          )}
        </div>
      </header>

      {/* tabIndex -1 lets the skip link move focus here */}
      <main id="main" tabIndex={-1} className="mx-auto max-w-6xl px-4 py-8 focus:outline-none sm:px-6 sm:py-10">
        <Outlet />
      </main>
    </div>
  )
}
