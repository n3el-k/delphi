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

### API contract (draft, confirm in M0)

| Method + path | Owner | Returns |
| ------------- | ----- | ------- |
| `GET /api/me` | Param | Seeded learner: name, GitHub login, current level |
| `GET /api/levels` | Param | 4 levels: name, AI policy, what it unlocks, status (done, current, locked), gate requirements |
| `GET /api/dashboard` | Param | Skill map scores, current project + ticket, progress to next level |
| `GET /api/portfolio` | Param | Projects, levels, concepts shown, security fixes, PR links |
| `GET /api/gates/{id}` | Neel | PR link, review summary, findings, questions, status |
| `POST /api/gates/{id}/answers` | Neel | Per question: score, explanation, next hint. Overall: passed |
| `POST /api/reviews/{id}/flag` | Neel | Records a learner's disagreement with a reason |
| `POST /webhooks/github` | Neel | GitHub only. Verifies the signature, starts a review |

Neel's gate code calls Param's `progress.record_gate_pass(...)` when a learner passes.

### Data model (draft, confirm in M0)

Learner · Level · Project · Ticket · Submission (one PR) · Review · Finding · Gate · Question · Answer · SkillScore · Flag

## Who's doing what

| Task | Owner | Status |
| ---- | ----- | ------ |
| DB schema + API contract | Both | todo |
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

## Open questions

- Deadline and hours left, so we can set milestone times.
- Project name.
- Demo hosting: run locally with the smee tunnel, or deploy (backend on Render or Fly, frontend on Vercel) so judges can try it?
- Claude API key: whose account, and are there hackathon credits?
- Who records and edits the demo video?
