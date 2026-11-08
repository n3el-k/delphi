# Delphi: know thy code

> AI writes code for you. Delphi makes sure you understand it. An AI senior reviewer won't approve your pull request until you can explain it.

Built at Hack the Change 2026 (Calgary), Prompt 2: developing in-demand skills in a changing job market.

## Team

- Neel Kochhar ([@n3el-k](https://github.com/n3el-k))
- Param ([@param-m1](https://github.com/param-m1))

## The problem

New developers "git push and pray". AI tools produce code that works, but they can't say what it does, and they can't spot the security flaws it quietly introduces. Entry-level work is the work AI now does, so what's left to learn is understanding, debugging, security judgment and breadth.

## What Delphi does

1. **Idea to tickets.** Describe a project in plain words. Claude turns it into 3-5 tickets that say *why* and what "done" means, never *how*.
2. **Real pull requests.** You write the code and open a PR on your own GitHub repo. A GitHub App reads the diff and replies with a Socratic review: questions, a security or correctness finding, and a hint ladder (concept, then where to look, then a small snippet). It never posts the corrected code.
3. **Comprehension gate.** Delphi asks 2-3 questions about *your* diff. A weak answer gets the next hint, not approval. Pass, and the bot approves the PR.
4. **Progress you can show.** The dashboard tracks your skill map across the stack, and the portfolio lists approved PRs and the security flaws you found and fixed.

Understanding is enforced at merge time, so it doesn't depend on which tools someone used locally. Every grade shows why, and any review, finding or grade can be flagged.

## Built for trust

- **Accessibility:** semantic HTML, labelled inputs, keyboard navigation with a visible focus ring, WCAG AA contrast, shadcn/ui (Radix) components.
- **Transparency:** every AI grade and finding carries its explanation. Hints are revealed one at a time by the server, so they can't be read early in devtools.
- **Privacy:** no emails, tokens or passwords stored. The diff is the learner's own practice-repo code.
- **Security:** every endpoint validates a Pydantic model, every webhook's `X-Hub-Signature-256` is verified, secrets live only in `.env`.

## Tech stack

- **Backend:** Python 3.12, FastAPI, SQLModel + SQLite, uv
- **AI:** Claude (`claude-opus-5-5`) through the Anthropic SDK, with structured output checked against Pydantic models
- **GitHub:** a GitHub App for webhooks, review comments and approvals
- **Frontend:** Vite, React, TypeScript, Tailwind, shadcn/ui, React Router

## Where it goes next

Levels: beginners start with no AI code generation and earn more AI help as they prove understanding. Calgary nonprofits post real work as tickets, and higher-level learners take them on. The nonprofit board in the app is a preview with made-up organisations and sample data.

## Getting started

```bash
git clone https://github.com/n3el-k/hackthechange2026.git
cd hackthechange2026
```

### Backend

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
cp .env.example .env              # then fill it in (see below)
uv sync                           # install dependencies
uv run python -m app.seed         # create the database with the demo learner
uv run fastapi dev app/main.py    # API on http://localhost:8000, interactive docs at /docs
uv run pytest                     # tests; GitHub and Claude are faked, so no keys needed
```

What goes in `.env` (names only are in `.env.example`; never commit the real file):

- `ANTHROPIC_API_KEY`: a Claude API key.
- `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`, `GITHUB_PRIVATE_KEY_PATH`, `GITHUB_WEBHOOK_SECRET`: from a GitHub App with **Pull requests: read and write** and **Contents: read**, subscribed to the **Pull request** event, and installed on the learner's practice repo. Keep the downloaded `.pem` key outside the repo.
- `SMEE_URL`: a channel from [smee.io](https://smee.io), set as the GitHub App's webhook URL, so GitHub can reach your laptop.

To receive webhooks locally, run **one** smee client next to the API (two clients deliver every event twice):

```bash
npx -y smee-client --url "$SMEE_URL" --target http://localhost:8000/webhooks/github
```

Rerun `uv run python -m app.seed` after pulling a change to `backend/app/models.py`: it wipes and recreates the database.

### Frontend

You need Node 20+. Start the backend first.

```bash
cd frontend
npm install
npm run dev        # app on http://localhost:5173
npm run gen:api    # after a change to backend/app/schemas.py: regenerate the TypeScript types
```

The app talks to `http://localhost:8000` by default. To point it somewhere else, set `VITE_API_URL` in `frontend/.env` (see `frontend/.env.example`).

## How we worked

- Planning lives in [plans/](plans/), starting with [plans/project-plan.md](plans/project-plan.md).
- The git workflow is in [CONTRIBUTING.md](CONTRIBUTING.md).
