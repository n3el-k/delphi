import { ExternalLink as ExternalIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// The reviewer is a GitHub App. Its public name is the end of github.com/apps/<name>.
const APP_SLUG = import.meta.env.VITE_GITHUB_APP_SLUG || 'hackthechange2026'
const INSTALL_URL = `https://github.com/apps/${APP_SLUG}/installations/new`

/** How to get from nothing to a reviewed PR: making a repo, installing the reviewer, and the gate. */
export default function HelpPage() {
  return (
    <div className="space-y-8">
      <title>Help · Hack the Change</title>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Getting started</h1>
        <p className="text-muted-foreground">
          You write the code. The AI reviewer reads your pull requests, asks about them, and approves them once you've
          shown you understand them.
        </p>
      </div>

      <ol className="space-y-4">
        <Step number={1} title="Make a repo on GitHub">
          <p>
            Create an empty repository on GitHub. We don't make it for you: setting up a repo is part of what you're
            learning.
          </p>
          <ExternalLink href="https://github.com/new">Create a repository on GitHub</ExternalLink>
        </Step>

        <Step number={2} title="Install the reviewer on it">
          <p>
            The reviewer is a GitHub App. Install it on your new repo, so GitHub tells us when you open a pull request.
            Choose <strong>Only select repositories</strong> and pick your repo: it doesn't need access to anything else.
          </p>
          <ExternalLink href={INSTALL_URL}>Install the reviewer</ExternalLink>
        </Step>

        <Step number={3} title="Start a project">
          <p>
            Describe your idea and paste your repo's name, like <code>your-name/todo</code>. You'll get tickets that
            explain why each piece matters and how you'll know it's done, but never how to build it.
          </p>
          <Link to="/projects/new" className="text-sm underline underline-offset-4">
            Start a project
          </Link>
        </Step>

        <Step number={4} title="Open a pull request for a ticket">
          <p>
            Work on a branch, push it, and open a pull request. Put the ticket's number in the description, like{' '}
            <code>Ticket: #1</code>, so the reviewer knows what you're working on.
          </p>
          <p>
            In about 30 seconds the reviewer comments on your pull request with questions and a link back here. Answer
            the questions in your own words. Each answer needs a score of 70 or more. If one falls short, you get a hint
            and another try. If the reviewer finds a security problem, fix it and push again first.
          </p>
          <p>Once every answer passes, the reviewer approves your pull request and your skill map goes up.</p>
        </Step>
      </ol>

      <section aria-labelledby="problems-heading" className="space-y-3">
        <h2 id="problems-heading" className="text-xl font-semibold">
          If something goes wrong
        </h2>
        <div className="divide-y rounded-lg border">
          <Question q="I opened a pull request and nothing happened">
            Check that the reviewer is installed on that repo (step 2), and that the repo name on your project matches
            it exactly. If it still doesn't show up, push another commit to the branch: each push asks for a new review.
          </Question>
          <Question q="My project's repo name is wrong">
            Start a new project with the right name. Projects can't be edited yet.
          </Question>
          <Question q="I think the reviewer graded me unfairly">
            Use <strong>Flag this grade</strong> under the answer. A person looks at every flag. A flag never changes
            your score by itself.
          </Question>
          <Question q="Can the AI write the code for me?">
            No. It reviews, asks questions and gives hints, from the idea behind a fix to where to look to a short
            example. It never writes your code.
          </Question>
        </div>
      </section>
    </div>
  )
}

function Step({ number, title, children }: { number: number; title: string; children: ReactNode }) {
  return (
    <li>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2 className="flex items-center gap-3 text-lg">
              <span
                aria-hidden="true"
                className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm text-primary-foreground"
              >
                {number}
              </span>
              {title}
            </h2>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">{children}</CardContent>
      </Card>
    </li>
  )
}

/** A native disclosure: keyboard and screen reader support come built in. */
function Question({ q, children }: { q: string; children: ReactNode }) {
  return (
    <details className="group px-4 py-3">
      <summary className="cursor-pointer rounded font-medium focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
        {q}
      </summary>
      <p className="mt-2 text-muted-foreground">{children}</p>
    </details>
  )
}

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-sm underline underline-offset-4"
    >
      {children}
      <ExternalIcon aria-hidden="true" className="size-3.5" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}
