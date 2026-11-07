# Project plan

The shared source of truth for scope, architecture and who's doing what. The product itself (problem, thesis, levels, learning loop) is in [brief.md](brief.md). Day-to-day notes go in your own file ([neel.md](neel.md), [param.md](param.md)).

## At a glance

- **Event:** Hack the Change 2026, Calgary. Prompt 2 (skills and networks in a changing job market).
- **Team:** Neel owns the GitHub + AI pipeline. Param owns the learner app.
- **Deadline:** _TBD. Fill in, then set the milestone times below._
- **Demo centrepiece:** the live GitHub loop. If only one thing works, it's this.

## Scope

### Must have (in priority order)

1. [ ] **Live GitHub loop:** Level 1 PR → webhook → AI posts a Socratic review with at least one security or correctness finding → learner answers comprehension questions in our app → pass → PR approved, skill profile and level progress update.
2. [ ] **Level map:** all 4 levels visible, current one active, higher ones locked, each showing what it unlocks (including AI permissions).
3. [ ] **Learner dashboard:** skill map across the stack, current project and ticket, progress to the next level.
4. [ ] **Experience report / portfolio page.**
5. [ ] **Transparency:** every AI grade shows why, and any review can be flagged. This is a non-negotiable and part of the Accessibility sidepot story.

### Seeded or faked

- Auth and signup: one seeded learner, no real login.
- Assessment and notifications.
- Levels 2–4 content: shown on the level map, not playable.

### Nice to have (only once the must-haves work end to end)

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
                                                         └──► update skill profile + level progress
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

### The three Claude calls (Neel)

Each call returns a Pydantic model, so the API, the DB and the frontend all share one shape.

1. **Review** (diff, ticket, level policy) → summary, findings (kind: security or correctness, vulnerability class, file, line, a Socratic question, a hint ladder of concept → where to look → small snippet), policy flags.
2. **Questions** (diff) → 2–3 questions about the learner's own lines.
3. **Grade** (question, diff, answer) → score, passed, explanation of the grade, next hint if failed.

Rules: never full corrected code (enforced in the prompt and by rejecting long snippets). Check `stop_reason` for refusals. Keep a cached known-good review of the demo PR as a fallback for judging.

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
      learner.py     # me, levels, dashboard, portfolio     (Param)
    services/
      github.py      # GitHub App client                    (Neel)
      reviewer.py    # Claude prompts and calls             (Neel)
      progress.py    # skill + level progress updates       (Param)
  tests/
  pyproject.toml
  .env.example
frontend/
  src/
    pages/           # LevelMap, Dashboard, Gate, Portfolio
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

**Param's endpoints**

```
GET /api/me
→ { name, github_login, current_level: { number, name } }

GET /api/levels
→ [{ number, name, ai_policy, unlocks: [str],
     requirements: { projects, min_gate_score, security_fixes },
     status: "done" | "current" | "locked" }]

GET /api/dashboard
→ { skills: [{ area, score }],
    current_project: { id, title },
    current_ticket: { id, title, why, acceptance_criteria: [str] },
    open_gate_id: int | null,
    progress: { projects: { done, required },
                security_fixes: { done, required } } }

GET /api/portfolio
→ { learner: { name, github_login },
    levels_completed: [int],
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
- **After a pass, the frontend refetches** the `dashboard` and `levels` queries instead of reading progress from the answers response.
- Neel's gate code calls Param's `progress.record_gate_pass(learner_id, submission_id)` on a pass. It bumps SkillScores from `Ticket.skill_areas` and counts resolved security Findings.

### Data model (v1, proposed by Neel, Param to confirm)

Content (seeded):

```
Level         id, number (1–4), name, ai_policy, unlocks (JSON list),
              required_projects, min_gate_score, required_security_fixes
Project       id, level_id → Level, title, description, repo_full_name
Ticket        id, project_id → Project, title, why, acceptance_criteria (JSON list),
              skill_areas (JSON list), label (core | delegable | null)
```

Learner:

```
Learner       id, name, github_login (unique), current_level_id → Level
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
- **Computed, not stored:** level status, progress to the next level and the portfolio come from queries.
- **No promotion logic in the MVP.** The learner stays on Level 1. The requirement columns on `Level` feed the level map and the dashboard progress bar.

## Who's doing what

| Task | Owner | Status |
| ---- | ----- | ------ |
| DB schema + API contract | Both | doing |
| GitHub App, webhook, AI review | Neel | todo |
| Comprehension gate: questions, grading, PR approval | Neel | todo |
| Demo practice repo + demo PR | Neel | todo |
| Data model, seed data, learner APIs, progress logic | Param | todo |
| Level map, dashboard, gate screen, portfolio | Param | todo |
| Grade transparency + flag a review | Neel (API), Param (UI) | todo |
| Accessibility pass | Param | todo |
| Demo video, Devpost, README | Both | todo |

Status: `todo` · `doing` · `done` · `blocked`. Task-level detail lives in each person's file.

## Milestones

Each one ends in something we can demo.

| # | When | Milestone | Demo at the end |
| - | ---- | --------- | --------------- |
| M0 | _..._ | Skeleton + contract | The React app shows the seeded learner from FastAPI. A GitHub webhook ping reaches the backend. |
| M1 | _..._ | Live review + level map | Open a PR on the demo repo and the bot posts a Socratic + security review. The level map and dashboard show seeded data. |
| M2 | _..._ | Gate loop end to end | Answer the questions in the app, get a hint on a weak answer, pass, and the PR is approved and progress updates. **MVP centrepiece done.** |
| M3 | _..._ | Full learner journey | Portfolio page, "why this grade" and flag a review. **Feature freeze after this.** |
| M4 | _..._ | Polish + submit | Accessibility pass, visual polish, demo video, Devpost, public repo. |

## Demo and judging

**How we hit each criterion:**

| Criterion | Our answer |
| --------- | ---------- |
| Innovation & Creativity | AI access is earned level by level, and understanding is enforced at merge time instead of being an opt-in "learning mode". |
| Impact & Relevance | Teaches what AI can't replace (debugging, security judgment, full-stack breadth). Networks come from matched teams, volunteer pros and nonprofit clients. |
| Feasibility & Scalability | Runs on real GitHub PRs with a standard stack. SQLModel moves to Postgres without code changes. |
| Technical Execution | A live end-to-end loop, structured AI output, a stable seeded demo with fallbacks. |
| UX & Design | A clear level map and dashboard, shadcn/ui polish, accessible from the start. |

**Sidepots:**

- **Best Local Impact (Benevity):** nonprofit commissions give Calgary nonprofits a pipeline of motivated learners, with AI review before anything ships.
- **Best in Accessibility (Clio):** semantic, keyboard-navigable, high-contrast UI. Every grade is explained and can be flagged. We store minimal data.

**Demo script (draft, 2–5 min):**

1. The problem in 20 seconds: "git push and pray".
2. The level map: AI is something you earn.
3. Live: the learner opens a PR on the Level 1 calculator that uses `eval()` on input. The bot replies with a Socratic question and a code-injection finding.
4. The learner fixes it and answers the comprehension questions in the app. One weak answer gets a hint, then they pass.
5. The bot approves the PR. The dashboard skill map and level progress update, and the portfolio shows the security fix.
6. The vision: Levels 3–4, nonprofit commissions in Calgary, matched teams.

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
| _Proposed:_ SQLite via SQLModel | No setup, can move to Postgres later | 2026-11-07 |
| _Proposed:_ Claude `claude-opus-5-5` with `messages.parse` + Pydantic | Output always matches our schema | 2026-11-07 |
| _Proposed:_ GitHub App for webhook + reviews | Bot identity, can approve PRs | 2026-11-07 |
| _Proposed:_ Schema and API contract v1 (see Architecture) | Lets us both start building against one shape. Param to confirm | 2026-11-07 |
| _Proposed:_ Gate created by the webhook in `reviewing` state, frontend polls | The bot's link works immediately, and the frontend gets a clear loading state | 2026-11-07 |
| _Proposed:_ API only returns hints already revealed | Hidden hints in the payload could be read in devtools | 2026-11-07 |
| No level promotion in the MVP, only progress toward Level 2 | Levels 2–4 aren't playable. Progress is all the demo needs | 2026-11-07 |

## Open questions

- Deadline and hours left, so we can set milestone times.
- Project name.
- Demo hosting: run locally with the smee tunnel, or deploy (backend on Render or Fly, frontend on Vercel) so judges can try it?
- Claude API key: whose account, and are there hackathon credits?
- Who records and edits the demo video?
