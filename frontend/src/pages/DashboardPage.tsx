import { ArrowRight, ClipboardCheck, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import { LogoMark } from '@/components/Logo'
import { ErrorState, Loading } from '@/components/states'
import TicketCard from '@/components/TicketCard'
import { Button } from '@/components/ui/button'
import { useApi, type Dashboard } from '@/lib/api'

export default function DashboardPage() {
  const { data, error, reload } = useApi<Dashboard>('/api/dashboard')

  if (!data) {
    return error ? (
      <ErrorState title="Couldn't load your dashboard" error={error} onRetry={reload} />
    ) : (
      <Loading label="Loading your dashboard" />
    )
  }

  const done = data.tickets.filter((t) => t.status === 'done').length

  return (
    <div className="space-y-8">
      <title>Dashboard · Delphi</title>

      {data.open_gate_id !== null && (
        <section
          aria-labelledby="review-heading"
          className="flex flex-wrap items-center gap-4 rounded-xl border border-peach bg-peach-soft p-5"
        >
          <span aria-hidden="true" className="flex size-10 items-center justify-center rounded-full bg-peach">
            <ClipboardCheck className="size-5" />
          </span>
          {/* basis-60: on a phone the text keeps its width and the button wraps below it */}
          <div className="min-w-0 flex-1 basis-60">
            <h2 id="review-heading" className="font-sans text-base font-semibold tracking-normal">
              A review is waiting for you
            </h2>
            <p className="text-sm text-muted-foreground">
              Answer the reviewer's questions about your code to get your pull request approved.
            </p>
          </div>
          <Button asChild>
            <Link to={`/gates/${data.open_gate_id}`}>
              Answer the questions
              <ArrowRight aria-hidden="true" />
            </Link>
          </Button>
        </section>
      )}

      {data.current_project ? (
        <div className="grid gap-8 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <section aria-labelledby="project-heading" className="space-y-3">
              <p className="text-sm font-medium text-jungle-ink">Current project</p>
              <h1 id="project-heading" className="text-3xl font-semibold sm:text-4xl">
                {data.current_project.title}
              </h1>
              <p className="max-w-prose text-muted-foreground">{data.current_project.description}</p>
              <div className="flex items-center gap-3 pt-1">
                <div aria-hidden="true" className="h-2 max-w-60 flex-1 rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-jungle"
                    style={{ width: `${(done / Math.max(data.tickets.length, 1)) * 100}%` }}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  {done} of {data.tickets.length} tickets done
                </p>
              </div>
            </section>

            <section aria-labelledby="tickets-heading" className="space-y-3">
              <h2 id="tickets-heading" className="text-xl font-semibold">
                Tickets
              </h2>
              <ol className="space-y-3">
                {data.tickets.map((ticket) => (
                  <li key={ticket.id}>
                    <TicketCard ticket={ticket} status={ticket.status} />
                  </li>
                ))}
              </ol>
            </section>
          </div>

          <aside className="space-y-6">
            <SkillMap skills={data.skills} />
            <AiRule />
          </aside>
        </div>
      ) : (
        <div className="grid gap-8 lg:grid-cols-3">
          <Welcome />
          <aside className="space-y-6">
            <SkillMap skills={data.skills} />
            <AiRule />
          </aside>
        </div>
      )}
    </div>
  )
}

/** The first thing a new learner (and a judge) sees: what Delphi is, and one way in. */
function Welcome() {
  return (
    <section
      aria-labelledby="welcome-heading"
      className="relative overflow-hidden rounded-2xl bg-forest p-8 text-white sm:p-10 lg:col-span-2"
    >
      <LogoMark className="absolute -right-6 -bottom-6 size-48 opacity-15 [&_rect]:fill-transparent" />
      <p className="text-sm font-medium text-peach">Welcome to Delphi</p>
      <h1 id="welcome-heading" className="mt-2 text-4xl font-semibold sm:text-5xl">
        Know thy code.
      </h1>
      <p className="mt-4 max-w-prose text-white/85">
        Describe what you want to build and you'll get tickets that explain why each piece matters. You write the code.
        When you open a pull request, an AI senior reviewer asks about it, and approves it once you've shown you
        understand it.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button asChild size="lg" className="bg-peach text-foreground hover:bg-peach/90 focus-visible:ring-peach">
          <Link to="/projects/new">
            Start your first project
            <ArrowRight aria-hidden="true" />
          </Link>
        </Button>
        <Button
          asChild
          size="lg"
          variant="ghost"
          className="text-white hover:bg-white/10 hover:text-white focus-visible:ring-peach"
        >
          <Link to="/help">How it works</Link>
        </Button>
      </div>

      <ol className="mt-10 grid gap-4 border-t border-white/15 pt-6 sm:grid-cols-3">
        {[
          ['Describe your idea', 'Get tickets with the why and how you’ll know it’s done. Never the how.'],
          ['Open a pull request', 'The AI reviewer checks it for security and correctness, and asks about it.'],
          ['Explain your code', 'Answer in your own words. Pass, and your PR is approved.'],
        ].map(([title, text], i) => (
          <li key={title} className="flex gap-3">
            <span
              aria-hidden="true"
              className="flex size-7 shrink-0 items-center justify-center rounded-full bg-peach text-sm font-semibold text-foreground"
            >
              {i + 1}
            </span>
            <span>
              <span className="block font-medium">{title}</span>
              <span className="text-sm text-white/80">{text}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}

function SkillMap({ skills }: { skills: Dashboard['skills'] }) {
  return (
    <section aria-labelledby="skills-heading" className="rounded-xl border bg-card p-5 shadow-xs">
      <h2 id="skills-heading" className="text-xl font-semibold">
        Skill map
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">Grows each time you pass a review.</p>
      <ul className="mt-4 space-y-3">
        {skills.map((skill) => (
          <li key={skill.area} className="space-y-1.5">
            <div className="flex justify-between text-sm">
              <span className="font-medium capitalize">{skill.area}</span>
              <span className="text-muted-foreground tabular-nums">{skill.score} / 100</span>
            </div>
            {/* The bar is decoration: the numbers above already say it */}
            <div aria-hidden="true" className="h-2 rounded-full bg-muted">
              <div className="h-2 rounded-full bg-jungle" style={{ width: `${skill.score}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** The one rule, stated where the learner works, so the AI's role is never a surprise. */
function AiRule() {
  return (
    <section aria-labelledby="rule-heading" className="rounded-xl border bg-secondary p-5">
      <h2 id="rule-heading" className="flex items-center gap-2 font-sans text-base font-semibold tracking-normal">
        <ShieldCheck aria-hidden="true" className="size-5 text-jungle-ink" />
        The AI rule
      </h2>
      <p className="mt-2 text-sm text-muted-foreground">
        The AI turns your idea into tickets, reviews your code, asks questions and gives hints. It never writes your
        code.
      </p>
    </section>
  )
}
