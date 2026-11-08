import { ExternalLink } from 'lucide-react'
import { ErrorState, Loading } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useApi, type Portfolio } from '@/lib/api'

/** The experience report: work that passed review, and security problems the learner fixed. */
export default function PortfolioPage() {
  const { data, error, reload } = useApi<Portfolio>('/api/portfolio')

  if (!data) {
    return error ? (
      <ErrorState title="Couldn't load your portfolio" error={error} onRetry={reload} />
    ) : (
      <Loading label="Loading your portfolio" />
    )
  }

  return (
    <div className="space-y-8">
      <title>Portfolio · Delphi</title>
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">{data.learner.name}'s experience report</h1>
        <p className="text-muted-foreground">
          Every item here passed an AI code review where {data.learner.name} explained their own code.{' '}
          <a
            href={`https://github.com/${data.learner.github_login}`}
            target="_blank"
            rel="noreferrer"
            className="underline underline-offset-4"
          >
            @{data.learner.github_login} on GitHub<span className="sr-only"> (opens in a new tab)</span>
          </a>
        </p>
      </div>

      <section aria-labelledby="work-heading" className="space-y-4">
        <h2 id="work-heading" className="text-xl font-semibold">
          Approved work
        </h2>
        {data.projects.length === 0 ? (
          <p className="text-muted-foreground">Nothing yet. Pass your first code review and it shows up here.</p>
        ) : (
          <ul className="space-y-4">
            {data.projects.map((entry) => (
              <li key={entry.pr_url}>
                <Card>
                  <CardHeader>
                    <CardTitle>
                      <h3>{entry.title}</h3>
                    </CardTitle>
                    <CardDescription>
                      Approved{' '}
                      <time dateTime={entry.approved_at}>{new Date(entry.approved_at).toLocaleDateString()}</time>
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {entry.concepts.length > 0 && (
                      <ul aria-label="Skills shown" className="flex flex-wrap gap-2">
                        {entry.concepts.map((concept) => (
                          <li key={concept}>
                            <Badge variant="secondary" className="capitalize">
                              {concept}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    )}
                    <PrLink url={entry.pr_url} />
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="fixes-heading" className="space-y-4">
        <h2 id="fixes-heading" className="text-xl font-semibold">
          Security fixes
        </h2>
        {data.security_fixes.length === 0 ? (
          <p className="text-muted-foreground">No security fixes yet.</p>
        ) : (
          <ul className="space-y-4">
            {data.security_fixes.map((fix) => (
              <li key={`${fix.pr_url}-${fix.file}-${fix.vuln_class}`}>
                <Card>
                  <CardHeader>
                    <CardTitle>
                      <h3>{fix.vuln_class}</h3>
                    </CardTitle>
                    <CardDescription>
                      <code>{fix.file}</code>
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-sm">
                    <p>{fix.explanation}</p>
                    <PrLink url={fix.pr_url} />
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function PrLink({ url }: { url: string }) {
  return (
    <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm underline underline-offset-4">
      View the pull request
      <ExternalLink aria-hidden="true" className="size-3.5" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  )
}
