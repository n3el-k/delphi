# Neel's plan

Working notes. Only Neel edits this file. Anything decided goes in [project-plan.md](project-plan.md).

## My area

The GitHub + AI pipeline: everything that talks to GitHub or Claude. I meet Param's half at the API contract in the project plan.

## Now

M1 and M2 are merged (#7–#10). The backend runs the whole loop: PR → webhook → Socratic review with findings and questions → answers graded in the app → bot approves the PR → skill map updates. Tested live once end to end on `n3el-k/level1-calculator`.

Frontend skeleton (`feat/frontend-skeleton`): all four pages working against the backend, plain shadcn/ui look. Param takes over layout and polish.

Next: run the whole loop live through the app (idea → tickets → demo PR → gate → pass), then record the backup video.

## Next

### M0: Skeleton + contract

- [x] Agree `models.py`, `schemas.py` and the API contract with Param (merged in PR #2)
- [x] ~~FastAPI skeleton~~ Param built it in PR #2
- [x] Create the GitHub App: pull requests read/write, contents read, subscribed to `pull_request`. Private key path and webhook secret go in `.env`
- [x] smee.io channel forwarding to local `/webhooks/github`. Confirm a ping arrives
- [x] Claude API key in `.env`. One test `messages.parse` call that returns a Pydantic model
- [x] Demo practice repo with a demo PR that has a real flaw: `eval()` on user input (code injection). No longer seeded: on stage it's linked through the idea form
- [x] Check the demo PR still fits the expression ticket in `FALLBACK_TICKETS` (`CalculatorError`, divide by zero), and add an input-length cap to `demo/evaluate-fix` (see Notes). All four acceptance criteria hold on the fix branch. The cap (200 characters) is a second commit on `demo/evaluate-fix`, so the fix push is now 2 commits

### M1: Live review + tickets

- [x] `POST /webhooks/github`: verify `X-Hub-Signature-256`, handle `pull_request` opened, reopened and synchronize, return 202 fast and do the work in a background task
- [x] Fetch the PR diff and match it to the learner and ticket (the learner comes from the repo linked to their project, not the PR author): `Ticket: #<id>` in the PR description, else the learner's first ticket that isn't done. On stage, read the id off the dashboard and type it into the demo PR
- [x] `reviewer.generate_tickets(idea)`: Claude turns a project idea into 3–5 tickets (title, why, acceptance criteria, skill areas), never the how, with the core-feature ticket first. Param's `POST /api/projects` calls it. Falls back to the calculator's tickets if Claude fails (see M3)
- [x] Review prompt returning the `Review` model: Socratic questions, security and correctness findings (class, file, line), hint ladder, policy flags against the one fixed AI rule (the AI never writes your code)
- [x] ~~Don't create a second `Finding`~~ Each push keeps its own findings as history, and on a pass only the newest copy of each problem (kind, file, CWE number) is marked resolved, so a fix counts once
- [x] Enforce "no full corrected code": a rule in the prompt, plus rejecting snippets longer than about 5 lines (one retry, then `ReviewerError`)
- [x] Post the review on the PR as the bot, with a link to the gate page in our app. Only the concept hint goes on GitHub, so `hints_revealed` starts at 1
- [x] Save the review and findings to the DB

### M2: Gate loop end to end

- [x] Generate 2–3 comprehension questions from the learner's own diff and store them as a Gate. They come from the review call, one set per push (`Question.review_id`), and a push after a finding gets a question about the fix
- [x] `GET /api/gates/{id}` for Param's gate screen
- [x] `POST /api/gates/{id}/answers`: grade each answer with Claude (score 0–100, explanation, next hint). The gate passes when every question's latest score is ≥ 70. A fail moves up the hint ladder, it doesn't approve
- [x] On a pass: approve the PR through the GitHub API (pinned to `head_sha`), set `Gate.status = passed` and `Submission.status = approved`, mark fixed findings `resolved`, then call Param's `progress.record_gate_pass(...)`. Leave `passed_at` to it
- [ ] Run the full loop live 3+ times (1 so far: n3el-k/level1-calculator#2, through the API with curl). Record a backup video of it

### M3: Transparency + hardening

- [x] Return the "why" with every grade and finding. Add `POST /api/reviews/{id}/flag` (flags the whole review, one finding or one grade. Stored for a person to look at, it never changes a score or the gate)
- [x] Timeouts and retries on Claude and GitHub calls. Handle `stop_reason == "refusal"`. `_parse` has the timeouts, one SDK retry and the refusal check, and every GitHub call has a 10s timeout
- [x] Cached fallback tickets for the calculator: `generate_tickets` returns them with `is_fallback=True` when Claude fails, with a 20s timeout and one SDK retry (~40s worst case). It never raises: cut-off JSON and unexpected errors fall back too, and a bad key is logged as an error. The expression ticket comes first, matching the demo PR
- [ ] ~~Cached review and questions for the demo PR~~ Dropped for now: test the whole app first, and only add it if Claude turns out to be unreliable (see Decisions)
- [x] Agree who adds `is_fallback`: Param adds it to the `POST /api/projects` response and a `Project` column, in the `POST /api/projects` PR

### M4: Polish + submit

- [x] Security check of our own repo: no secrets in history, every endpoint validated. Every `.env` value and the private key checked against all branches' history: none found. `*.pem` and `*.db` added to `.gitignore`. Every endpoint takes a Pydantic model or bounded int ids (the webhook validates after its signature check). Fixed in #12: ids over 2⁶³ overflowed SQLite and returned a 500
- [x] Backend setup steps in the README
- [ ] Demo video and Devpost, with Param

## Blocked / need from Param

- None. The `gate_score` and `TicketStatus` notes from #10 are done: Param switched `gate_score` to the minimum and moved `TicketStatus` into `models.py` in #14, and #13 counts only the latest push's questions

## Wiring into the skeleton (PR #2 is merged)

`reviewer.py` was built standalone, before the skeleton existed. Now:

- [x] Add `anthropic` to `backend/pyproject.toml` (shared file, Param told in the PR #2 approval)
- [x] Add `anthropic_api_key` to `config.Settings` and pass it to `anthropic.Anthropic(api_key=...)`, so a plain `uv run fastapi dev` server finds the key in `.env`
- [x] Replace the `SkillAreaName` Literal in `reviewer.py` with `models.SkillArea`
- [x] Map `ReviewResult` onto `Review` + `Finding` rows (`hints` = `[concept, where_to_look, snippet]`) ~~and `TicketSet` onto `Project` + `Ticket`~~ Review side done in the webhook PR. Tickets are Param's `POST /api/projects`
- [x] Run `scripts/try_reviewer.py` with plain `uv run python -m scripts.try_reviewer`. Works with `ANTHROPIC_API_KEY` unset in the shell, so the key comes from settings: 5 real tickets in 14.9s, the expression ticket first
- [x] Add the run and test commands to the Commands section of CLAUDE.md

## Notes

- Claude: `claude-opus-5-5`. `client.messages.parse(..., output_format=Model)`, then read `response.parsed_output`.
- `reviewer.py` uses `client.beta.messages.parse` with `fallbacks="default"` (beta `server-side-fallback-2026-07-01`), so if Opus 5.5's safety classifier declines security-flavoured code, the API retries on another model in the same call.
- First runs (2026-11-07): tickets take ~15s, the review ~29s, which fits inside the 60s timeout. On the `eval()` PR it found CWE-94 at `calculator.py:32`, the `1/0` crash, other inputs that crash or slip through, and the missing tests. On `demo/evaluate-fix` it found one real issue: `_work_out` recurses once per operator, so a very long sum crashes with `RecursionError`. To keep the fix push clean in the demo, add an input-length cap to `demo/evaluate-fix`.
- With the cap (2026-11-07): the fix push's review has no `RecursionError` and one correctness finding instead (`1e999` gives `inf`, not a `CalculatorError`). Correctness doesn't block the pass, and the first question asks the learner to explain the `eval()` fix. Review took ~45s.
