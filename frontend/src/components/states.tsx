// The loading and error states every page uses, so they look and sound the same everywhere.

import { CircleAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/** Grey placeholder blocks while the first data loads. Screen readers hear `label`. */
export function Loading({ label }: { label: string }) {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">{label}…</span>
      <Skeleton className="h-8 w-1/3" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-28 w-full" />
    </div>
  )
}

/** A failed load, with the reason and a way to try again. */
export function ErrorState({ title, error, onRetry }: { title: string; error: Error; onRetry?: () => void }) {
  return (
    <Alert variant="destructive" role="alert">
      <CircleAlert aria-hidden="true" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{error.message}</p>
        {onRetry && (
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetry}>
            Try again
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}
