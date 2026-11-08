# Project plan

The shared source of truth for scope, architecture and who's doing what. The product itself (problem, thesis, levels, learning loop) is in [brief.md](brief.md). Day-to-day notes go in your own file ([neel.md](neel.md), [param.md](param.md)).

## At a glance

- **Event:** Hack the Change 2026, Calgary. Prompt 2 (skills and networks in a changing job market).
- **Team:** Neel owns the GitHub + AI pipeline. Param owns the learner app.
- **Deadline:** _TBD. Fill in, then set the milestone times below._
- **Demo centrepiece:** the live GitHub loop. If only one thing works, it's this.

## Scope

### Must have (in priority order)

There are no levels in the MVP. One fixed AI rule applies to everyone: the AI turns your idea into tickets, reviews and tutors, and never writes your code.

1. [ ] **Live GitHub loop:** PR on a ticket → webhook → AI posts a Socratic review with at least one security or correctness finding → learner answers comprehension questions in our app → pass → PR approved, skill profile updates.
2. [ ] **Project idea → tickets:** the learner types a project idea and links their repo. Claude turns the idea into 3–5 tickets with the why and acceptance criteria (never the how), spread across the stack. The learner sees Claude's summary of how it understood their idea alongside the tickets. The idea is one free-text box (no intake form), and its placeholder guides the learner: "Who's it for, and what should they be able to do? e.g. A shift board where food bank volunteers sign up for shifts and coordinators post them."
3. [ ] **Learner dashboard:** skill map across the stack, the current project, and its tickets with their status.
4. [ ] **Experience report / portfolio page.**
5. [ ] **Transparency:** every AI grade shows why, and any review can be flagged. This is a non-negotiable and part of the Accessibility sidepot story.

### Seeded or faked

- Auth and signup: one seeded learner, no real login.
- Assessment and notifications.
- No seeded projects. The learner starts with an empty dashboard and creates their first project from an idea. On stage we type a calculator idea. The `eval()` finding comes from the demo PR's code, which we write in advance, so it doesn't depend on the live tickets.
- Fallback tickets: if Claude is slow or down, `generate_tickets` returns cached calculator tickets (the expression ticket first) with `is_fallback: true`, and the UI labels them as example tickets with a "Try again" button.
- The demo practice repo is created on GitHub in advance and linked through the idea form like any learner's repo. It isn't seeded.

### Nice to have (only once the must-haves work end to end)

- [ ] Levels, part 1: a static level map. All 4 levels shown as a roadmap with the learner on Level 1, the others locked, and what each unlocks. Keep the AI rule in one place so it can become one rule per level.
- [ ] Levels, part 2: real promotion between levels.
- [ ] Level 3–4 delegation: CORE/DELEGABLE ticket labels, review of AI-written code.
- [ ] Nonprofit commissions screen with seeded tickets, for the Local Impact pitch. Use made-up nonprofits unless a real one has said yes.
- [ ] Matched teams and volunteer pros.

### Out of scope

- Real accounts, payments, multi-tenant anything.
- Detecting which AI tools someone used locally. The comprehension gate is the enforcement.

## Architecture (proposed, needs both OKs)

### How the pieces talk

```
Learner's practice repo on GitHub
   │  pull_request webhook
   ▼
FastAPI  /webhooks/github ──diff──► Claude: review + questions ──► DB
   │                                                              ▲
   └── posts review comment on the PR (as the GitHub App bot)     │
                                                                  │
Learner ──► React app ──► FastAPI /api/... ───────────────────────┘
               │
               └─ submits answers ─► Claude grades ─► pass? ─► approve PR on GitHub
                                                         └──► update skill profile

Learner ──► project idea ──► Claude: tickets ──► DB
```

### Stack

| Layer | Choice | Why |
| ----- | ------ | --- |
| Backend | Python 3.12, FastAPI, uv | Team choice. Pydantic validates every request body for free (one of our non-negotiables). |
| Database | SQLite via SQLModel | No setup, one file, easy to seed and reset. The same models run on Postgres later (scalability story for judges). |
| AI | Claude API through the Anthropic Python SDK, model `claude-opus-5-5` | Strongest reviewer. `client.messages.parse(..., output_format=<Pydantic model>)` returns output checked against our schema, so no fragile JSON parsing. |
| GitHub | A GitHub App, called with PyGithub (or plain httpx) | Reviews come from a bot account, which reads well in the demo, and the app can approve PRs. |
| Frontend | Vite + React + TypeScript, Tailwind, shadcn/ui, React Router, TanStack Query, lucide-react | FastAPI is the backend, so the frontend only needs to be a plain React app with no server layer to fight. shadcn/ui gives polished components built on Radix, so keyboard and screen reader support come mostly for free. Claude Code is very fluent in this stack. |
| Webhook in dev | smee.io | GitHub needs a public URL to deliver webhooks to a laptop. |

### The four Claude calls (Neel)

Each call returns a Pydantic model, so the API, the DB and the frontend all share one shape.

1. **Tickets** (project idea) → a project title, a one-paragraph summary of the idea (who it's for and the core features Claude inferred), and 3–5 tickets: title, why, acceptance criteria, skill areas. Never the how.
2. **Review** (diff, ticket, AI rule) → summary, findings (kind: security or correctness, vulnerability class, file, line, a Socratic question, a hint ladder of concept → where to look → small snippet), policy flags.
3. **Questions** (diff) → 2–3 questions about the learner's own lines.
4. **Grade** (question, diff, answer) → score 0–100, passed, explanation of the grade, next hint if failed.

Rules: never full corrected code (enforced in the prompt and by rejecting long snippets). Check `stop_reason` for refusals. Keep cached known-good output as a fallback for judging: the calculator's tickets, and the review and questions for the demo PR.

### Folder structure

```
backend/
  app/
    main.py          # FastAPI app, CORS, routers          (shared)
    config.py        # settings from .env                   (shared)
    db.py            # engine + session                     (shared)
    models.py        # SQLModel tables                      (shared, agree in M0)
    schemas.py       # request/response models = contract   (shared, agree in M0)
    seed.py          # seed data                            (Param)
    routers/
      webhooks.py    # POST /webhooks/github                (Neel)
      gates.py       # comprehension gate endpoints         (Neel)
      learner.py     # me, projects, dashboard, portfolio   (Param)
    services/
      github.py      # GitHub App client                    (Neel)
      reviewer.py    # Claude prompts and calls             (Neel)
      progress.py    # skill progress updates               (Param)
  tests/
  pyproject.toml
  .env.example
frontend/
  src/
    pages/           # NewProject, Dashboard, Gate, Portfolio
    components/
    lib/api.ts       # typed client for the contract
  package.json
```

Shared files change only in small PRs, and you tell the other person first.

### API contract (v1, proposed by Neel, Param to confirm)

**Conventions**

- snake_case JSON end to end. The frontend generates its TypeScript types from `/openapi.json` with `openapi-typescript`, so `schemas.py` is the single source of truth.
- No learner ID in URLs. There's one seeded learner, so every endpoint means "me".
- Errors use FastAPI's default `{ "detail": ... }`: 404 for unknown IDs, 422 for invalid bodies.

**Param's endpoints** (no-levels changes proposed by Neel, Param to confirm)

```
GET /api/me
→ { name, github_login }

POST /api/projects
← { idea, repo_full_name }                   idea: 1–1000 chars, repo: "owner/name"
→ { id, title, description, is_fallback, tickets: [{ id, title, why, acceptance_criteria: [str] }] }
                                             description: Claude's one-paragraph summary of the idea (who it's for, core features), at most 500 chars
                                             is_fallback: true when Claude was unavailable and these are the cached example tickets
                                             calls Neel's reviewer.generate_tickets(idea), which never raises

GET /api/dashboard
→ { skills: [{ area, score }],
    current_project: { id, title, description } | null,
    tickets: [{ id, title, why, acceptance_criteria: [str],
                status: "todo" | "in_review" | "done" }],
    open_gate_id: int | null }

GET /api/portfolio
→ { learner: { name, github_login },
    projects: [{ title, pr_url, approved_at, concepts: [str] }],
    security_fixes: [{ vuln_class, file, pr_url, explanation }] }
```

**Neel's endpoints**

```
GET /api/gates/{id}
→ { id, status: "reviewing" | "open" | "passed",
    pr_url, ticket_title,
    review: { id, summary, is_fallback } | null,
    findings: [{ id, kind, vuln_class, file, line, explanation,
                 socratic_question, hints: [str], resolved }],
    questions: [{ id, text, file, line,
                  last_answer: { text, score, passed, explanation, next_hint } | null }] }

POST /api/gates/{id}/answers
← { answers: [{ question_id, text }] }       text: 1–2000 chars
→ { passed, results: [{ question_id, score, passed, explanation, next_hint }] }

POST /api/reviews/{id}/flag
← { reason, finding_id?, answer_id? }        reason: 1–1000 chars
→ { id, created_at }

POST /webhooks/github                        GitHub only. Verifies the signature, returns 202, reviews in the background
```

**How it behaves**

- **The gate exists before the review finishes.** The webhook creates the Submission and Gate straight away with `status: "reviewing"`, so the link in the bot's comment always works. The gate page polls (TanStack Query `refetchInterval`) until the status is `open`.
- **`hints` only holds hints already revealed.** Sending all three and hiding them in the UI would let a learner read the snippet in devtools. Each failed answer reveals the next hint.
- **Answers are submitted in one batch.** Only the failed ones need answering again.
- **After a pass, the frontend refetches** the `dashboard` query instead of reading progress from the answers response.
- **A PR names its ticket.** The PR description says `Ticket: #<id>`. If it doesn't, the webhook uses the learner's first ticket that isn't done.
- **A gate passes** when every question's latest score is at or above one fixed minimum (70).
- Neel's gate code sets `Gate.status = passed` and `Submission.status = approved`, marks fixed findings `resolved`, then calls Param's `progress.record_gate_pass(learner_id, submission_id)`. That function stamps `passed_at` (so a second call does nothing), bumps SkillScores from `Ticket.skill_areas` and counts resolved security Findings.

### Data model (v1, proposed by Neel, Param to confirm)

Projects and tickets (from the learner's idea):

```
Project       id, learner_id → Learner, idea, title, description, repo_full_name,
              is_fallback (bool)
              (description holds Claude's summary of the idea, shown on the dashboard, ≤ 500 chars.
               is_fallback marks the cached example tickets, so the label survives a reload)
Ticket        id, project_id → Project, position, title, why,
              acceptance_criteria (JSON list), skill_areas (JSON list),
              label (core | delegable | null)
```

`Level` is out of the MVP. It comes back with the level map (see Nice to have).

Learner:

```
Learner       id, name, github_login (unique)
SkillScore    id, learner_id → Learner, area (enum), score 0–100
              unique (learner_id, area)
              area: frontend, backend, database, git, debugging, security, testing
```

GitHub loop:

```
Submission    id, learner_id, ticket_id, repo_full_name, pr_number, pr_url,
              head_sha, diff (text), status, created_at
              unique (repo_full_name, pr_number)
              status: reviewing | awaiting_gate | approved
Review        id, submission_id, head_sha, summary, policy_flags (JSON),
              github_comment_id, is_fallback (bool), created_at
Finding       id, review_id, kind (security | correctness), vuln_class,
              file, line, explanation, socratic_question,
              hints (JSON: [concept, where_to_look, snippet]),
              hints_revealed (int), resolved (bool)
Gate          id, submission_id (unique), status (reviewing | open | passed), passed_at
Question      id, gate_id, finding_id (nullable), text, file, line
Answer        id, question_id, text, score, passed, explanation, next_hint, created_at
Flag          id, review_id, finding_id (nullable), answer_id (nullable), reason, created_at
```

Why it's shaped this way:

- **One Review per push, not per PR.** Each `synchronize` push gets a new Review, which gives a before-and-after history for the portfolio ("found `eval()` injection, fixed it in the next commit").
- **Hints are a JSON list on Finding**, since the ladder is always three steps and only `hints_revealed` changes.
- **Every attempt is an Answer row**, so "why this grade" covers every attempt, not only the last.
- **The diff is stored on Submission** so grading doesn't need a GitHub call per answer. It's the learner's own practice-repo code.
- **Minimal data:** no emails, tokens or passwords.
- **Computed, not stored:** ticket status and the portfolio come from queries.
- **No levels in the MVP.** No `Level` table, no promotion, no "progress to the next level".

## Who's doing what

| Task | Owner | Status |
| ---- | ----- | ------ |
| DB schema + API contract | Both | done |
| GitHub App, webhook, AI review | Neel | doing |
| Claude call: project idea → tickets | Neel | doing |
| Comprehension gate: questions, grading, PR approval | Neel | todo |
| Demo practice repo + demo PR | Neel | done |
| Data model, seed data, learner APIs, progress logic | Param | doing |
| New-project form, dashboard, gate screen, portfolio | Param | todo |
| Grade transparency + flag a review | Neel (API), Param (UI) | todo |
| Accessibility pass | Param | todo |
| Demo video, Devpost, README | Both | todo |

Status: `todo` · `doing` · `done` · `blocked`. Task-level detail lives in each person's file.

## Milestones

Each one ends in something we can demo.

| # | When | Milestone | Demo at the end |
| - | ---- | --------- | --------------- |
| M0 | _..._ | Skeleton + contract | The React app shows the seeded learner from FastAPI. A GitHub webhook ping reaches the backend. |
| M1 | _..._ | Live review + tickets | Open a PR on the demo repo and the bot posts a Socratic + security review. Type a project idea and get tickets. The dashboard shows them. |
| M2 | _..._ | Gate loop end to end | Answer the questions in the app, get a hint on a weak answer, pass, and the PR is approved and the skill map updates. **MVP centrepiece done.** |
| M3 | _..._ | Full learner journey | Portfolio page, "why this grade" and flag a review. **Feature freeze after this.** |
| M4 | _..._ | Polish + submit | Accessibility pass, visual polish, demo video, Devpost, public repo. |

## Demo and judging

**How we hit each criterion:**

| Criterion | Our answer |
| --------- | ---------- |
| Innovation & Creativity | An AI senior reviewer that won't merge your PR until you prove you understand it. Understanding is enforced at merge time instead of being an opt-in "learning mode", and the AI never writes your code. |
| Impact & Relevance | Teaches what AI can't replace (debugging, security judgment, full-stack breadth). Networks come from matched teams, volunteer pros and nonprofit clients. |
| Feasibility & Scalability | Runs on real GitHub PRs with a standard stack. SQLModel moves to Postgres without code changes. |
| Technical Execution | A live end-to-end loop, structured AI output, a stable seeded demo with fallbacks. |
| UX & Design | From idea to tickets in one step, a clear dashboard, shadcn/ui polish, accessible from the start. |

**Sidepots:**

- **Best Local Impact (Benevity):** nonprofit commissions give Calgary nonprofits a pipeline of motivated learners, with AI review before anything ships.
- **Best in Accessibility (Clio):** semantic, keyboard-navigable, high-contrast UI. Every grade is explained and can be flagged. We store minimal data.

**Demo script (draft, 2–5 min):**

1. The problem in 20 seconds: "git push and pray".
2. The learner types a calculator idea, links the practice repo, and gets tickets that explain the why, never the how. The expression ticket comes first.
3. Live: the learner opens a PR on the calculator that uses `eval()` on input. The bot replies with a Socratic question and a code-injection finding.
4. The learner fixes it and answers the comprehension questions in the app. One weak answer gets a hint, then they pass.
5. The bot approves the PR. The ticket shows as done, the dashboard skill map updates, and the portfolio shows the security fix.
6. The vision: levels where you earn more AI help, nonprofit commissions in Calgary, matched teams.

Record a backup of the live loop in case the venue Wi-Fi fails.

**Submission checklist:**

- [ ] Before going public, decide what to remove: `plans/`, `CLAUDE.md`, `.claude/`. Deleting them in a new commit leaves them in the history, so squash the history or publish a clean copy if they need to be fully gone.
- [ ] Check that no secrets were ever committed (history included)
- [ ] Repo public (if required)
- [ ] Once public, turn on branch protection for `main` (free private repos can't have it)
- [ ] README filled in
- [ ] Demo video (2–5 min)
- [ ] Submitted on Devpost with the public GitHub link
- [ ] Devpost title is exactly `TEAM ID-TEAM NAME - PROJECT NAME` (wrong format fails prescreening)

## Decisions

Record decisions here so neither of us re-argues them at 3am.

| Decision | Why | Date |
| -------- | --- | ---- |
| Neel owns the GitHub + AI pipeline, Param owns the learner app | The two halves meet at one API contract, so we can build in parallel | 2026-11-07 |
| FastAPI backend | Team preference | 2026-11-07 |
| Vite + React + TS + Tailwind + shadcn/ui frontend | Least friction next to a separate backend, accessible components out of the box | 2026-11-07 |
| SQLite via SQLModel | No setup, can move to Postgres later. Built in PR #2 | 2026-11-07 |
| Claude `claude-opus-5-5` with `messages.parse` + Pydantic | Output always matches our schema. Built in the reviewer service | 2026-11-07 |
| _Proposed:_ GitHub App for webhook + reviews | Bot identity, can approve PRs | 2026-11-07 |
| Schema and API contract v1 (see Architecture) | Lets us both start building against one shape. Param built the learner side against it in PR #2 | 2026-11-07 |
| _Proposed:_ Gate created by the webhook in `reviewing` state, frontend polls | The bot's link works immediately, and the frontend gets a clear loading state | 2026-11-07 |
| _Proposed:_ API only returns hints already revealed | Hidden hints in the payload could be read in devtools | 2026-11-07 |
| ~~No level promotion in the MVP, only progress toward Level 2~~ Replaced by the row below | | 2026-11-07 |
| Every change, `plans/` included, goes through a PR reviewed by the other person | Keeps `main` working and both of us aware of every change | 2026-11-07 |
| No levels in the MVP. The learner gives a project idea, Claude makes the tickets, and one fixed rule applies: the AI never writes your code. Levels come back if there's time | Promotion can't be shown in a demo, and the GitHub loop is what has to work. The ladder stays in the pitch as the vision | 2026-11-07 |
| Answer scores are 0–100. A gate passes when every question's latest score is ≥ 70 | One rule for passing, with skill points only on a real pass | 2026-11-07 |
| A PR names its ticket with `Ticket: #<id>` in the description, falling back to the first ticket not done. `generate_tickets` puts the core-feature ticket first, so the fallback lands on it. On stage, read the id off the dashboard and type it into the demo PR | `Submission.ticket_id` is required, and the webhook needs to know which ticket the PR is for. Matching by title is fragile with live Claude output | 2026-11-07 |
| _Proposed:_ Project idea is one free-text box, no intake form. Claude returns a summary of how it understood the idea plus the tickets, and the dashboard shows the summary | Least friction for the learner and the smallest contract change. Showing the summary makes the AI's reading of the idea transparent. If it misread the idea, the learner submits a new one (no editing in the MVP) | 2026-11-07 |
| No seeded projects. The seed is one learner and a starting skill map. The dashboard's current project is the newest one that isn't done | A seeded project would hide the one created from an idea on stage. The `eval()` finding comes from the demo PR's code, not the ticket | 2026-11-07 |
| If Claude fails, `generate_tickets` returns cached calculator tickets with `is_fallback: true`, after a 20s timeout and one retry (~40s worst case). It never raises. Param adds `is_fallback` to the `POST /api/projects` response and a `Project` column | Retrying alone doesn't help when the Wi-Fi, key or credits are the problem. The flag lets the UI say so honestly, and the column keeps the label after a reload | 2026-11-07 |
| The idea summary is at most 500 characters: Claude is asked for 400 and the result is trimmed at a sentence end | The dashboard card needs a predictable size. Trimming beats throwing away good tickets over a long summary | 2026-11-07 |
| _Proposed:_ The comprehension questions come from the review call, not a fourth call. Each push gets its own 2–3 questions (`Question.review_id`), and the gate shows the latest push's. A security finding on the latest push blocks the pass until it's fixed, and the next push asks the learner to explain the fix | One Claude call keeps the gate opening at ~30s on stage, and questions can point at findings. The brief says a security issue has to be fixed and explained, not just answered around. Older questions stay as grade history | 2026-11-07 |

## Open questions

- Deadline and hours left, so we can set milestone times.
- Project name.
- Demo hosting: run locally with the smee tunnel, or deploy (backend on Render or Fly, frontend on Vercel) so judges can try it?
- Claude API key: whose account, and are there hackathon credits?
- Who records and edits the demo video?