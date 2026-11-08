import { HandHeart, Info, Lock, MapPin, ShieldCheck } from 'lucide-react'
import { Medallion } from '@/components/Logo'

// A preview of the nonprofit board, for the Local Impact pitch. Not wired to the backend.
// Every organisation here is made up: we don't name real Calgary nonprofits unless one has agreed.
type Commission = {
  org: string
  neighbourhood: string
  cause: string
  title: string
  why: string
  skills: string[]
  size: string
}

const COMMISSIONS: Commission[] = [
  {
    org: 'Chinook Pantry Collective',
    neighbourhood: 'Forest Lawn',
    cause: 'Food security',
    title: 'Volunteer shift board',
    why: 'Coordinators fill weekend shifts by group text, and half the messages get lost. Volunteers need one place to see open shifts and sign up.',
    skills: ['frontend', 'backend', 'database'],
    size: '4 tickets · about 2 weeks',
  },
  {
    org: 'Foothills Literacy Circle',
    neighbourhood: 'Bowness',
    cause: 'Education',
    title: 'Tutor and learner matching',
    why: 'Adult learners wait weeks for a tutor because matching happens in a spreadsheet. A simple sign-up and match list would cut the wait.',
    skills: ['backend', 'database', 'security'],
    size: '5 tickets · about 3 weeks',
  },
  {
    org: 'Kestrel Animal Rescue',
    neighbourhood: 'Inglewood',
    cause: 'Animal welfare',
    title: 'Adoptable animals page',
    why: 'Adoption posts only live on social media, where they get buried. A page that staff can update would keep every animal visible.',
    skills: ['frontend', 'testing'],
    size: '3 tickets · about 1 week',
  },
  {
    org: 'Welcome Table Newcomer Society',
    neighbourhood: 'Marlborough',
    cause: 'Newcomer support',
    title: 'Resource directory in five languages',
    why: 'New Calgarians miss services they qualify for because the list is a printed English handout. A searchable, translated directory would reach more families.',
    skills: ['frontend', 'database'],
    size: '4 tickets · about 2 weeks',
  },
  {
    org: 'Northside Tool Share',
    neighbourhood: 'Highland Park',
    cause: 'Community',
    title: 'Tool lending tracker',
    why: 'Tools go missing because loans are written on a clipboard. Members need to see what is available and when borrowed tools are due back.',
    skills: ['backend', 'database', 'testing'],
    size: '4 tickets · about 2 weeks',
  },
  {
    org: 'Green Lane Garden Society',
    neighbourhood: 'Kensington',
    cause: 'Environment',
    title: 'Garden plot waitlist',
    why: 'The waitlist is an email inbox, so nobody knows where they stand. A fair, visible queue would save the volunteers hours every spring.',
    skills: ['frontend', 'backend', 'security'],
    size: '3 tickets · about 1 week',
  },
]

export default function NonprofitsPage() {
  return (
    <div className="space-y-8">
      <title>Calgary nonprofits · Delphi</title>

      <section
        aria-labelledby="board-heading"
        className="relative overflow-hidden rounded-2xl bg-forest p-8 text-white sm:p-10"
      >
        <Medallion className="absolute -top-16 -right-16 size-72 opacity-15" />
        <p className="flex items-center gap-2 text-sm font-medium text-peach">
          <MapPin aria-hidden="true" className="size-4" />
          Calgary
        </p>
        <h1 id="board-heading" className="mt-2 max-w-2xl text-4xl font-semibold sm:text-5xl">
          Build for Calgary nonprofits.
        </h1>
        <p className="mt-4 max-w-prose text-white/85">
          Local nonprofits post real work as tickets. Learners who've passed reviews on their own projects take them on, and Delphi's reviewer
          checks every pull request before it ships. Nonprofits get software they couldn't afford, and learners get real
          clients for their portfolio.
        </p>
        <ul className="mt-6 flex flex-wrap gap-x-8 gap-y-3 text-sm">
          <li className="flex items-center gap-2">
            <HandHeart aria-hidden="true" className="size-5 text-peach" />
            Free for nonprofits
          </li>
          <li className="flex items-center gap-2">
            <ShieldCheck aria-hidden="true" className="size-5 text-peach" />
            Every PR reviewed for security
          </li>
          <li className="flex items-center gap-2">
            <Lock aria-hidden="true" className="size-5 text-peach" />
            For learners with approved work
          </li>
        </ul>
      </section>

      {/* Honest about what this page is: judges and learners shouldn't think these are real postings */}
      <p className="flex items-start gap-2 rounded-lg border border-peach bg-peach-soft p-4 text-sm">
        <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        <span>
          <strong>Preview.</strong> These are sample listings from made-up organisations, to show how the board will
          work.
        </span>
      </p>

      <section aria-labelledby="open-heading" className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="open-heading" className="text-2xl font-semibold">
            Open commissions
          </h2>
          <p className="text-sm text-muted-foreground">
            {COMMISSIONS.length} projects from {COMMISSIONS.length} organisations
          </p>
        </div>
        <p className="max-w-prose text-sm text-muted-foreground">
          Several learners can work on the same commission. Taking one on doesn't guarantee the nonprofit will use your
          code: if someone else's version fits their needs better, they may choose that one. Your approved work still
          counts toward your portfolio.
        </p>

        <ul className="grid gap-4 md:grid-cols-2">
          {COMMISSIONS.map((c) => (
            <li key={c.title}>
              <article className="flex h-full flex-col rounded-xl border bg-card p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <span className="font-medium text-jungle-ink">{c.cause}</span>
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <MapPin aria-hidden="true" className="size-3.5" />
                    {c.neighbourhood}
                  </span>
                </div>
                <h3 className="mt-2 text-lg font-semibold">{c.title}</h3>
                <p className="text-sm text-muted-foreground">{c.org}</p>
                <p className="mt-3 text-sm">{c.why}</p>

                <div className="mt-auto pt-4">
                  <ul aria-label="Skills" className="flex flex-wrap gap-2">
                    {c.skills.map((skill) => (
                      <li key={skill} className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium capitalize">
                        {skill}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-sm">
                    <span className="text-muted-foreground">{c.size}</span>
                    <span className="flex items-center gap-1.5 rounded-full bg-peach px-2.5 py-0.5 text-xs font-medium">
                      <Lock aria-hidden="true" className="size-3" />
                      After 15 approved PRs
                    </span>
                  </div>
                </div>
              </article>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="post-heading" className="rounded-xl border bg-secondary p-6">
        <h2 id="post-heading" className="text-xl font-semibold">
          Run a Calgary nonprofit?
        </h2>
        <p className="mt-2 max-w-prose text-sm text-muted-foreground">
          Describe what you need in plain words, the same way learners describe their own ideas. Delphi turns it into
          tickets, matches it with learners, and reviews every change before it reaches you. Posting opens after the
          hackathon.
        </p>
      </section>
    </div>
  )
}
