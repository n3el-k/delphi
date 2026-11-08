import { NavLink, Outlet } from 'react-router'
import { useApi, type Me } from '@/lib/api'
import { cn } from '@/lib/utils'

const links = [
  // `end` stops "/" from also counting as active on every other page
  { to: '/', label: 'Dashboard', end: true },
  { to: '/projects/new', label: 'New project', end: false },
  { to: '/portfolio', label: 'Portfolio', end: false },
]

/** The frame around every page: a skip link, the nav and the learner's name. */
export default function Layout() {
  const me = useApi<Me>('/api/me')

  return (
    <div className="min-h-svh bg-background text-foreground">
      {/* Keyboard users can jump straight past the nav. Hidden until it gets focus. */}
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:ring-2 focus:ring-ring"
      >
        Skip to content
      </a>

      <header className="border-b">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <nav aria-label="Main">
            <ul className="flex flex-wrap gap-1">
              {links.map((link) => (
                <li key={link.to}>
                  {/* NavLink adds aria-current="page" to the link for the page you're on */}
                  <NavLink
                    to={link.to}
                    end={link.end}
                    className={({ isActive }) =>
                      cn(
                        'block rounded-md px-3 py-2 text-sm font-medium hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                        isActive && 'bg-muted',
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
            <p className="text-sm text-muted-foreground">
              {me.data.name} <span aria-hidden="true">·</span> @{me.data.github_login}
            </p>
          )}
        </div>
      </header>

      {/* tabIndex -1 lets the skip link move focus here */}
      <main id="main" tabIndex={-1} className="mx-auto max-w-4xl px-4 py-8 focus:outline-none">
        <Outlet />
      </main>
    </div>
  )
}
