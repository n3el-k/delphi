# Hack the Change 2026

Hackathon project by Neel ([@n3el-k](https://github.com/n3el-k)) and Param ([@param-m1](https://github.com/param-m1)). We're building a levels-based learning platform where new developers earn their way up to using AI. An AI senior reviewer won't accept a PR until the learner proves they understand it.

## Product

@plans/brief.md

## Plan

@plans/project-plan.md

## How to work with us

- **Propose before you build.** Before writing a big chunk of code (a new service, a new page, a schema change), say what you're about to build in a few lines and wait for an OK.
- **Explain as you go.** Give the reason for each key decision in a sentence or two. We're practising our own thesis, so we want to understand what we ship.
- **Keep it simple.** A working end-to-end demo beats extra features. Seed or fake anything outside the must-have scope.
- **Commit often**, in small commits with clear messages.

## Team workflow

Follow the rules in CONTRIBUTING.md:

@CONTRIBUTING.md

The ones that are easy to get wrong:

- **Never credit Claude.** No `Co-Authored-By: Claude` trailers in commits and no "Generated with Claude Code" lines in PR descriptions. Commits come from whoever you're working with, nobody else.
- **Never commit or push anything to `main`, `plans/` included.** Make a `feat/`, `fix/` or `chore/` branch, push it, and open a PR with `gh pr create`. Don't merge it until the other person has reviewed it.
- Pull `main` before starting work and before opening a PR.

## Who owns what

- Work out who you're working with: `gh api user --jq .login` returns `n3el-k` for Neel and `param-m1` for Param. Read that person's plan file at the start of a session (`plans/neel.md` or `plans/param.md`). If you can't tell who it is, ask.
- **Neel** owns the GitHub + AI pipeline: `backend/app/routers/webhooks.py`, `routers/gates.py`, `services/github.py`, `services/reviewer.py`.
- **Param** owns the learner app: `frontend/`, `backend/app/routers/learner.py`, `services/progress.py`, `seed.py`.
- **Shared:** `backend/app/main.py`, `config.py`, `db.py`, `models.py`, `schemas.py`. Change these only in small PRs, and tell the person you're working with to warn the other one first. If a change in someone else's area seems needed, say so instead of making it.
- Only edit the current person's plan file, never the other person's.
- Stay inside the must-have scope. If a request is a nice-to-have while must-haves are unfinished, or is out of scope, say so before building it.
- When a task is finished, tick it in the person's plan file and update its status in the "Who's doing what" table. When something gets decided, add it to the "Decisions" table.

## Rules for the code

We're a security and accessibility product, so our own code has to pass the standard we teach.

- **Secrets:** only in `.env` (gitignored). Add each variable name, not its value, to `.env.example`. Never log keys, tokens or webhook secrets.
- **Input validation:** every endpoint takes a Pydantic model. Verify the `X-Hub-Signature-256` header on every GitHub webhook.
- **Accessibility:** semantic HTML, a label on every input, full keyboard navigation with a visible focus ring, WCAG AA contrast. Use the shadcn/ui components rather than hand-rolled divs. Check each new page with axe or Lighthouse.
- **Transparency and privacy:** store only what the app needs. Every AI grade and finding carries its explanation, and every review can be flagged.
- **The AI reviewer never posts full corrected code.** Hints follow the ladder: concept → where to look → small illustrative snippet.
- **Demo stability:** seeded data and a timeout on every external call. No cached fallbacks: if Claude or GitHub fails, tell the learner plainly and let them retry.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLModel + SQLite, uv.
- **Claude:** Anthropic Python SDK, model `claude-opus-5-5`. Get structured output with `client.messages.parse(..., output_format=<Pydantic model>)` and read `response.parsed_output`. Check `stop_reason` for `"refusal"` before using the result.
- **Frontend:** Vite + React + TypeScript, Tailwind, shadcn/ui, React Router, lucide-react. No data-fetching library: pages call the API through `useApi` and `post` in `frontend/src/lib/api.ts`, typed from the backend's `/openapi.json`. It has to look great: consistent spacing, a real type scale, and loading, empty and error states on every page.

## Commands

Backend, from `backend/` (copy `.env.example` to `.env` and fill it in first):

```bash
uv sync                                   # install
uv run python -m app.seed                 # wipe the DB and seed the learner (rerun after a models.py change)
uv run fastapi dev app/main.py            # API on http://localhost:8000, docs at /docs
uv run pytest                             # tests (offline: GitHub and Claude are faked)
uv run python -m scripts.try_reviewer     # real Claude calls on the demo diff (costs a little)
```

The live demo, from the repo root. It runs git in a clone of `n3el-k/level1-calculator` next to this repo (set `DEMO_DIR` if it's elsewhere):

```bash
./scripts/demo.sh start 1                 # open a PR with the eval() flaw for ticket #1 (the id on the dashboard)
./scripts/demo.sh fix                     # push the fix to that PR
./scripts/demo.sh reset                   # close demo PRs, delete live/run-* branches, reseed the database
```

GitHub webhooks in dev: run exactly one smee client. Two clients deliver every event twice.

```bash
npx -y smee-client --url "$SMEE_URL" --target http://localhost:8000/webhooks/github
```

Frontend, from `frontend/` (the backend must be running):

```bash
npm install                               # install
npm run dev                               # app on http://localhost:5173
npm run gen:api                           # regenerate src/lib/api-types.ts after a schemas.py change
npm run build                             # typecheck and build
npm run lint                              # oxlint
```
