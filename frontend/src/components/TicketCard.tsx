import { ChevronRight } from 'lucide-react'
import type { NewTicket, TicketStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

const status: Record<TicketStatus, { label: string; className: string }> = {
  todo: { label: 'To do', className: 'bg-muted text-muted-foreground' },
  in_review: { label: 'In review', className: 'bg-peach text-foreground' },
  // Dark text on jungle green: white on it would only be 2.9:1
  done: { label: 'Done', className: 'bg-jungle text-foreground' },
}

export function StatusPill({ value }: { value: TicketStatus }) {
  return (
    <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-medium', status[value].className)}>
      {status[value].label}
    </span>
  )
}

/**
 * One ticket: why it matters and how you'll know it's done. Never how to build it.
 * `status` is left out on the new-project page, where nothing has started yet.
 */
export default function TicketCard({ ticket, status: value }: { ticket: NewTicket; status?: TicketStatus }) {
  return (
    <article className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold">{ticket.title}</h3>
        {value && <StatusPill value={value} />}
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{ticket.why}</p>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        {/* A native disclosure: keyboard and screen reader support come built in */}
        <details className="group w-full">
          <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded font-medium text-jungle-ink focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
            <ChevronRight aria-hidden="true" className="size-4 transition-transform group-open:rotate-90" />
            Done when ({ticket.acceptance_criteria.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-9 text-muted-foreground">
            {ticket.acceptance_criteria.map((criterion) => (
              <li key={criterion}>{criterion}</li>
            ))}
          </ul>
        </details>
        <p className="text-muted-foreground">
          {/* The webhook matches a PR to its ticket by this line in the PR description */}
          In your PR description:{' '}
          <code className="rounded bg-secondary px-1.5 py-0.5 font-medium text-foreground">Ticket: #{ticket.id}</code>
        </p>
      </div>
    </article>
  )
}
