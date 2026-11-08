import { Flag } from 'lucide-react'
import { useId, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { post, type FlagIn, type FlagOut } from '@/lib/api'

type Props = {
  reviewId: number
  /** Flag one finding instead of the whole review */
  findingId?: number
  /** Flag one grade instead of the whole review */
  answerId?: number
  /** What's being flagged, for the button: "this review", "this finding", "this grade" */
  what: string
}

/**
 * "I disagree with the AI." Opens a small form under the button, asks why, and sends it.
 * A flag is stored for a person to look at. It never changes a score or the gate.
 */
export default function FlagForm({ reviewId, findingId, answerId, what }: Props) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string>()
  // A unique id per form, so each label points at its own textarea
  const id = useId()

  async function send() {
    setSending(true)
    setError(undefined)
    try {
      const body: FlagIn = { reason, finding_id: findingId, answer_id: answerId }
      await post<FlagOut>(`/api/reviews/${reviewId}/flag`, body)
      setSent(true)
      setOpen(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSending(false)
    }
  }

  if (sent) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Thanks. A person will look at your flag. It doesn't change your grade.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-expanded={open}
        aria-controls={`${id}-form`}
        onClick={() => setOpen(!open)}
      >
        <Flag aria-hidden="true" />
        Flag {what}
      </Button>
      {open && (
        // A group, not a <form>: this sits inside the gate's answers form, and HTML doesn't
        // allow a form inside a form (its Send button would submit the answers instead).
        <div role="group" aria-label={`Flag ${what}`} id={`${id}-form`} className="space-y-2 rounded-lg border p-3">
          <Label htmlFor={`${id}-reason`}>Why do you disagree?</Label>
          <Textarea
            id={`${id}-reason`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            required
            maxLength={1000}
            autoFocus
          />
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={send} disabled={sending || reason.trim() === ''}>
              {sending ? 'Sending…' : 'Send flag'}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
