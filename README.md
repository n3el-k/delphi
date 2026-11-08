# Hack the Change 2026

> One-line pitch goes here.

## Team

- Neel Kochhar ([@n3el-k](https://github.com/n3el-k))
- [@param-m1](https://github.com/param-m1)

## The problem

_What are we solving, and for whom?_

## Our solution

_What did we build, and how does it work?_

## Tech stack

_TBD_

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

_Coming soon._

## How we work

- Planning lives in [plans/](plans/). Start with [plans/project-plan.md](plans/project-plan.md).
- The git workflow is in [CONTRIBUTING.md](CONTRIBUTING.md).
