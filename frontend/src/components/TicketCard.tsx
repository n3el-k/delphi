import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { NewTicket, TicketStatus } from '@/lib/api'

const statusLabel: Record<TicketStatus, string> = {
  todo: 'To do',
  in_review: 'In review',
  done: 'Done',
}

const statusVariant: Record<TicketStatus, 'outline' | 'secondary' | 'default'> = {
  todo: 'outline',
  in_review: 'secondary',
  done: 'default',
}

/**
 * One ticket: why it matters and how you'll know it's done. Never how to build it.
 * `status` is left out on the new-project page, where nothing has started yet.
 */
export default function TicketCard({ ticket, status }: { ticket: NewTicket; status?: TicketStatus }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3 className="flex flex-wrap items-center gap-2">
            {ticket.title}
            {status && <Badge variant={statusVariant[status]}>{statusLabel[status]}</Badge>}
          </h3>
        </CardTitle>
        <CardDescription>
          {/* The webhook matches a PR to its ticket by this line in the PR description */}
          Put <code className="rounded bg-muted px-1 py-0.5 text-foreground">Ticket: #{ticket.id}</code> in your PR
          description.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div>
          <h4 className="font-medium">Why</h4>
          <p className="text-muted-foreground">{ticket.why}</p>
        </div>
        <div>
          <h4 className="font-medium">Done when</h4>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            {ticket.acceptance_criteria.map((criterion) => (
              <li key={criterion}>{criterion}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}
