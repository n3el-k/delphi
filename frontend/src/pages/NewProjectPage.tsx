import { CircleAlert, Info } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import TicketCard from '@/components/TicketCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { post, type ProjectIn, type ProjectOut } from '@/lib/api'

const IDEA_PLACEHOLDER =
  "Who's it for, and what should they be able to do? e.g. A shift board where food bank volunteers sign up for shifts and coordinators post them."

export default function NewProjectPage() {
  const [idea, setIdea] = useState('')
  const [repo, setRepo] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string>()
  const [project, setProject] = useState<ProjectOut>()

  async function create(event?: FormEvent) {
    event?.preventDefault()
    setCreating(true)
    setError(undefined)
    try {
      const body: ProjectIn = { idea, repo_full_name: repo }
      setProject(await post<ProjectOut>('/api/projects', body))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-8">
      <title>New project · Hack the Change</title>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">New project</h1>
        <p className="text-muted-foreground">
          Describe your idea. You'll get tickets that explain why each piece matters, and you write the code.
        </p>
      </div>

      <form onSubmit={create} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="idea">Your project idea</Label>
          <Textarea
            id="idea"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder={IDEA_PLACEHOLDER}
            required
            maxLength={1000}
            rows={5}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="repo">GitHub repository</Label>
          <Input
            id="repo"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/name"
            aria-describedby="repo-help"
            required
          />
          <p id="repo-help" className="text-sm text-muted-foreground">
            An existing repo with the reviewer installed, like <code>your-name/todo</code>. We don't create it for you.{' '}
            <Link to="/help" className="underline underline-offset-4">
              How to set one up
            </Link>
          </p>
        </div>
        <Button type="submit" disabled={creating}>
          {creating ? 'Creating tickets…' : 'Create tickets'}
        </Button>
        {/* aria-live: screen readers announce this when it appears */}
        <p aria-live="polite" className="text-sm text-muted-foreground">
          {creating && 'Claude is reading your idea. This takes about 15 seconds.'}
        </p>
      </form>

      {error && (
        <Alert variant="destructive" role="alert">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>Couldn't create the project</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {project && (
        <section aria-labelledby="result-heading" className="space-y-4">
          <div className="space-y-1">
            <p className="text-sm text-muted-foreground">How we understood your idea</p>
            <h2 id="result-heading" className="text-xl font-semibold">
              {project.title}
            </h2>
            <p className="text-muted-foreground">{project.description}</p>
          </div>

          {project.is_fallback && (
            <Alert>
              <Info aria-hidden="true" />
              <AlertTitle>These are example tickets</AlertTitle>
              <AlertDescription>
                <p>The AI couldn't be reached, so these are ready-made tickets for a calculator.</p>
                <Button size="sm" variant="outline" className="mt-2" onClick={() => create()} disabled={creating}>
                  Try again
                </Button>
              </AlertDescription>
            </Alert>
          )}

          <ol className="space-y-4">
            {project.tickets.map((ticket) => (
              <li key={ticket.id}>
                <TicketCard ticket={ticket} />
              </li>
            ))}
          </ol>

          <Button asChild>
            <Link to="/">Go to your dashboard</Link>
          </Button>
        </section>
      )}
    </div>
  )
}
