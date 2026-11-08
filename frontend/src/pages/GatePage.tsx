import { CircleAlert, CircleCheck, ExternalLink, LoaderCircle, ShieldAlert } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import FlagForm from '@/components/FlagForm'
import { ErrorState, Loading } from '@/components/states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { post, useApi, type AnswersIn, type AnswersOut, type Finding, type Gate, type Question } from '@/lib/api'

// How often to check for news while the reviewer works or we wait for a fix push.
const POLL_MS = 4000

// The hint ladder, in the order hints are revealed.
const HINT_NAMES = ['Concept', 'Where to look', 'Small example']

/**
 * The comprehension gate: the bot's PR comment links here. Shows the AI's review of the
 * latest push, and the questions the learner has to answer before the PR is approved.
 */
export default function GatePage() {
  const { id } = useParams()
  const { data: gate, error, reload } = useApi<Gate>(`/api/gates/${id}`)

  // The backend won't take answers while a security finding is open: fix it and push first.
  const blocked = gate?.findings.some((f) => f.kind === 'security' && !f.resolved) ?? false
  const waiting = gate?.status === 'reviewing' || (gate?.status === 'open' && blocked)

  // While waiting, re-fetch every few seconds so the page updates by itself.
  useEffect(() => {
    if (!waiting) return
    const timer = setInterval(reload, POLL_MS)
    return () => clearInterval(timer)
  }, [waiting, reload])

  if (!gate) {
    return error ? (
      <ErrorState title="Couldn't load this review" error={error} onRetry={reload} />
    ) : (
      <Loading label="Loading the review" />
    )
  }

  return (
    <div className="space-y-8">
      <title>{`Review: ${gate.ticket_title} · Hack the Change`}</title>
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">Code review</p>
        <h1 className="text-2xl font-semibold">{gate.ticket_title}</h1>
        <a
          href={gate.pr_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-sm underline underline-offset-4"
        >
          View the pull request on GitHub
          <ExternalLink aria-hidden="true" className="size-3.5" />
          <span className="sr-only">(opens in a new tab)</span>
        </a>
      </div>

      {gate.status === 'reviewing' && (
        <Alert role="status">
          <LoaderCircle aria-hidden="true" className="animate-spin" />
          <AlertTitle>The reviewer is reading your code</AlertTitle>
          <AlertDescription>This takes about 30 seconds. The page updates by itself.</AlertDescription>
        </Alert>
      )}

      {gate.status === 'passed' && (
        <Alert role="status">
          <CircleCheck aria-hidden="true" />
          <AlertTitle>Passed. Your pull request is approved.</AlertTitle>
          <AlertDescription>
            <p>You explained your code and every question passed.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link to="/">Back to the dashboard</Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link to="/portfolio">See your portfolio</Link>
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* While a new push is being reviewed, the old review would only confuse */}
      {gate.status !== 'reviewing' && gate.review && (
        <>
          <section aria-labelledby="summary-heading" className="space-y-3">
            <h2 id="summary-heading" className="text-xl font-semibold">
              What the reviewer saw
            </h2>
            <p>{gate.review.summary}</p>
            <FlagForm reviewId={gate.review.id} what="this review" />
          </section>

          {gate.findings.length > 0 && (
            <section aria-labelledby="findings-heading" className="space-y-4">
              <h2 id="findings-heading" className="text-xl font-semibold">
                Findings
              </h2>
              <ul className="space-y-4">
                {gate.findings.map((finding) => (
                  <li key={finding.id}>
                    <FindingCard finding={finding} reviewId={gate.review!.id} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {gate.status === 'open' && blocked && (
            <Alert variant="destructive">
              <ShieldAlert aria-hidden="true" />
              <AlertTitle>Fix the security finding first</AlertTitle>
              <AlertDescription>
                Push a fix to your pull request. The reviewer will look again and ask you to explain it. This page
                updates by itself.
              </AlertDescription>
            </Alert>
          )}

          <Questions
            gate={gate}
            reviewId={gate.review.id}
            canAnswer={gate.status === 'open' && !blocked}
            onGraded={reload}
          />
        </>
      )}
    </div>
  )
}

function FindingCard({ finding, reviewId }: { finding: Finding; reviewId: number }) {
  const where = finding.line ? `${finding.file}, line ${finding.line}` : finding.file
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3 className="flex flex-wrap items-center gap-2">
            <Badge variant={finding.kind === 'security' ? 'destructive' : 'secondary'}>
              {finding.kind === 'security' ? 'Security' : 'Correctness'}
            </Badge>
            {finding.vuln_class ?? 'Something to check'}
            {finding.resolved && <Badge variant="outline">Fixed</Badge>}
          </h3>
        </CardTitle>
        <CardDescription>
          <code>{where}</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p>{finding.explanation}</p>
        <p className="font-medium">{finding.socratic_question}</p>
        {finding.hints.length > 0 && (
          <div>
            <h4 className="font-medium">Hints so far</h4>
            <ol className="mt-1 space-y-2">
              {finding.hints.map((hint, i) => (
                <li key={i}>
                  <span className="text-muted-foreground">{HINT_NAMES[i] ?? `Hint ${i + 1}`}: </span>
                  {/* The last rung is a small code snippet, so keep its line breaks */}
                  {i === 2 ? <pre className="mt-1 overflow-x-auto rounded-md bg-muted p-3 text-xs">{hint}</pre> : hint}
                </li>
              ))}
            </ol>
          </div>
        )}
        <FlagForm reviewId={reviewId} findingId={finding.id} what="this finding" />
      </CardContent>
    </Card>
  )
}

type QuestionsProps = {
  gate: Gate
  reviewId: number
  /** False while blocked by a security finding, or once the gate has passed */
  canAnswer: boolean
  /** Called after grading, so the page re-fetches and shows the new grades */
  onGraded: () => void
}

function Questions({ gate, reviewId, canAnswer, onGraded }: QuestionsProps) {
  // What the learner has typed, by question id
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [grading, setGrading] = useState(false)
  const [error, setError] = useState<string>()

  // Only questions without a passing answer need answering (again)
  const open = gate.questions.filter((q) => !q.last_answer?.passed)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setGrading(true)
    setError(undefined)
    try {
      const body: AnswersIn = {
        answers: open
          .filter((q) => (drafts[q.id] ?? '').trim() !== '')
          .map((q) => ({ question_id: q.id, text: drafts[q.id] })),
      }
      await post<AnswersOut>(`/api/gates/${gate.id}/answers`, body)
      setDrafts({})
      onGraded()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setGrading(false)
    }
  }

  if (gate.questions.length === 0) return null
  const nothingTyped = open.every((q) => (drafts[q.id] ?? '').trim() === '')

  return (
    <section aria-labelledby="questions-heading" className="space-y-4">
      <div className="space-y-1">
        <h2 id="questions-heading" className="text-xl font-semibold">
          Questions about your code
        </h2>
        <p className="text-sm text-muted-foreground">
          Answer in your own words. Each answer needs a score of 70 or more to pass.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-4">
        <ol className="space-y-4">
          {gate.questions.map((question, i) => (
            <li key={question.id}>
              <QuestionCard
                number={i + 1}
                question={question}
                reviewId={reviewId}
                canAnswer={canAnswer && !question.last_answer?.passed}
                draft={drafts[question.id] ?? ''}
                onDraft={(text) => setDrafts({ ...drafts, [question.id]: text })}
              />
            </li>
          ))}
        </ol>

        {canAnswer && open.length > 0 && (
          <>
            {error && (
              <p role="alert" className="flex items-center gap-2 text-sm text-destructive">
                <CircleAlert aria-hidden="true" className="size-4" />
                {error}
              </p>
            )}
            <Button type="submit" disabled={grading || nothingTyped}>
              {grading ? 'Grading…' : 'Submit answers'}
            </Button>
            <p aria-live="polite" className="text-sm text-muted-foreground">
              {grading && 'The reviewer is grading your answers. This takes up to 30 seconds.'}
            </p>
          </>
        )}
      </form>
    </section>
  )
}

type QuestionCardProps = {
  number: number
  question: Question
  reviewId: number
  canAnswer: boolean
  draft: string
  onDraft: (text: string) => void
}

function QuestionCard({ number, question, reviewId, canAnswer, draft, onDraft }: QuestionCardProps) {
  const answer = question.last_answer
  const fieldId = `answer-${question.id}`
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h3>
            {number}. {question.text}
          </h3>
        </CardTitle>
        {question.file && (
          <CardDescription>
            <code>{question.line ? `${question.file}, line ${question.line}` : question.file}</code>
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {answer && (
          <div className="space-y-2 rounded-lg border p-3">
            <p className="flex flex-wrap items-center gap-2">
              <span className="font-medium">Your last answer</span>
              <Badge variant={answer.passed ? 'default' : 'destructive'}>
                {answer.passed ? 'Passed' : 'Not yet'} · {answer.score} / 100
              </Badge>
            </p>
            <blockquote className="border-l-2 pl-3 text-muted-foreground">{answer.text}</blockquote>
            <div>
              <h4 className="font-medium">Why this grade</h4>
              <p>{answer.explanation}</p>
            </div>
            {answer.next_hint && (
              <div>
                <h4 className="font-medium">Hint</h4>
                <p>{answer.next_hint}</p>
              </div>
            )}
            <FlagForm reviewId={reviewId} answerId={answer.id} what="this grade" />
          </div>
        )}

        {canAnswer && (
          <div className="space-y-2">
            <Label htmlFor={fieldId}>{answer ? 'Try again' : 'Your answer'}</Label>
            <Textarea
              id={fieldId}
              value={draft}
              onChange={(e) => onDraft(e.target.value)}
              maxLength={2000}
              rows={4}
            />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
