import { ClipboardCheck } from 'lucide-react'
import { Link } from 'react-router'
import { ErrorState, Loading } from '@/components/states'
import TicketCard from '@/components/TicketCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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

  return (
    <div className="space-y-8">
      <title>Dashboard · Hack the Change</title>
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      {data.open_gate_id !== null && (
        <Alert>
          <ClipboardCheck aria-hidden="true" />
          <AlertTitle>A review is waiting for you</AlertTitle>
          <AlertDescription>
            <p>Answer the reviewer's questions to get your pull request approved.</p>
            <Button asChild size="sm" className="mt-2">
              <Link to={`/gates/${data.open_gate_id}`}>Open the review</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="project-heading" className="space-y-4">
        {data.current_project ? (
          <>
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">Current project</p>
              <h2 id="project-heading" className="text-xl font-semibold">
                {data.current_project.title}
              </h2>
              <p className="text-muted-foreground">{data.current_project.description}</p>
            </div>
            <ol className="space-y-4">
              {data.tickets.map((ticket) => (
                <li key={ticket.id}>
                  <TicketCard ticket={ticket} status={ticket.status} />
                </li>
              ))}
            </ol>
          </>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>
                <h2 id="project-heading">No project yet</h2>
              </CardTitle>
              <CardDescription>Describe what you want to build, and you'll get tickets to work through.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link to="/projects/new">Start a project</Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </section>

      <section aria-labelledby="skills-heading" className="space-y-3">
        <h2 id="skills-heading" className="text-xl font-semibold">
          Skill map
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {data.skills.map((skill) => (
            <li key={skill.area} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="font-medium capitalize">{skill.area}</span>
                <span className="text-muted-foreground">{skill.score} / 100</span>
              </div>
              {/* The bar is decoration: the numbers above already say it */}
              <div aria-hidden="true" className="h-2 rounded-full bg-muted">
                <div className="h-2 rounded-full bg-primary" style={{ width: `${skill.score}%` }} />
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
