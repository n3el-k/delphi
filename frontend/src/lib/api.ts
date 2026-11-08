// The one place the frontend talks to the backend.
//
// The types come from api-types.ts, which `npm run gen:api` generates from the backend's
// /openapi.json. So backend/app/schemas.py stays the single source of truth: change a field
// there, regenerate, and TypeScript points at every page that needs updating.

import { useCallback, useEffect, useState } from 'react'
import type { components } from './api-types'

type Schemas = components['schemas']
export type Me = Schemas['MeOut']
export type Dashboard = Schemas['DashboardOut']
export type Ticket = Schemas['TicketOut']
export type NewTicket = Schemas['TicketBase']
export type TicketStatus = Schemas['TicketStatus']
export type ProjectIn = Schemas['ProjectIn']
export type ProjectOut = Schemas['ProjectOut']
export type Gate = Schemas['GateOut']
export type Finding = Schemas['FindingOut']
export type Question = Schemas['QuestionOut']
export type AnswersIn = Schemas['AnswersIn']
export type AnswersOut = Schemas['AnswersOut']
export type FlagIn = Schemas['FlagIn']
export type FlagOut = Schemas['FlagOut']
export type Portfolio = Schemas['PortfolioOut']

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Reads finish fast. Writes can wait on Claude: tickets take ~15s (up to ~40s with the
// fallback), and grading three answers takes about as long as grading one.
const READ_TIMEOUT_MS = 15_000
const WRITE_TIMEOUT_MS = 90_000

/** A failed request, with a message that's safe to show the learner. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = READ_TIMEOUT_MS): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, signal: AbortSignal.timeout(timeoutMs) })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'TimeoutError') {
      throw new ApiError(0, 'The server took too long to answer. Try again.')
    }
    throw new ApiError(0, "Can't reach the server. Is the backend running?")
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  return response.json() as Promise<T>
}

/** FastAPI errors look like { detail: "..." }, or { detail: [{ msg }] } for a 422. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d: { msg: string }) => d.msg).join('. ')
  } catch {
    // not JSON: fall through to the generic message
  }
  return `Something went wrong (error ${response.status}).`
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(
    path,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
    WRITE_TIMEOUT_MS,
  )
}

/**
 * Fetch `path` when the page shows, and again whenever `reload()` is called.
 *
 * Pages check `data` first: while it's undefined, show the error if there is one, else a
 * loading state. A reload keeps the old data until the new data lands, so polling doesn't
 * flash a spinner every few seconds, and one failed poll doesn't wipe the page.
 */
export function useApi<T>(path: string) {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<ApiError>()
  // Bumping this number re-runs the effect below, which fetches again.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    // If the page goes away (or asks for another path) before the answer arrives,
    // ignore that late answer instead of showing it.
    let ignore = false
    request<T>(path).then(
      (result) => {
        if (ignore) return
        setData(result)
        setError(undefined)
      },
      (err: ApiError) => {
        if (!ignore) setError(err)
      },
    )
    return () => {
      ignore = true
    }
  }, [path, attempt])

  const reload = useCallback(() => setAttempt((n) => n + 1), [])

  return { data, error, reload }
}
