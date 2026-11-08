# Neel's plan

Working notes. Only Neel edits this file. Anything decided goes in [project-plan.md](project-plan.md).

## My area

The GitHub + AI pipeline: everything that talks to GitHub or Claude. I meet Param's half at the API contract in the project plan.

## Now

M1: `reviewer.py` has `generate_tickets` and `review_diff` working against the demo diff (on `feat/reviewer`). Next: the webhook and GitHub client. PR #2 is still being reworked.

## Next

### M0: Skeleton + contract

- [ ] Agree `models.py`, `schemas.py` and the API contract with Param (together, first thing)
- [x] ~~FastAPI skeleton~~ Param built it in PR #2
- [x] Create the GitHub App: pull requests read/write, contents read, subscribed to `pull_request`. Private key path and webhook secret go in `.env`
- [x] smee.io channel forwarding to local `/webhooks/github`. Confirm a ping arrives
- [x] Claude API key in `.env`. One test `messages.parse` call that returns a Pydantic model
- [x] Demo practice repo: the seeded calculator project, the default demo project. Prepare a demo PR with a real flaw, e.g. `eval()` on user input (code injection)

### M1: Live review + tickets

- [ ] `POST /webhooks/github`: verify `X-Hub-Signature-256`, handle `pull_request` opened and synchronize, return 200 fast and do the work in a background task
- [ ] Fetch the PR diff and match it to the learner and ticket: `Ticket: #<id>` in the PR description, else the learner's first ticket that isn't done
- [x] `reviewer.generate_tickets(idea)`: Claude turns a project idea into 3–5 tickets (title, why, acceptance criteria, skill areas), never the how. Param's `POST /api/projects` calls it. Fall back to the calculator's tickets if Claude fails (the fallback itself is still to do, see M3)
- [x] Review prompt returning the `Review` model: Socratic questions, security and correctness findings (class, file, line), hint ladder, policy flags against the one fixed AI rule (the AI never writes your code)
- [ ] Don't create a second `Finding` when a later push finds the same vulnerability again, so a fix is only counted once
- [x] Enforce "no full corrected code": a rule in the prompt, plus rejecting snippets longer than about 5 lines (one retry, then `ReviewerError`)
- [ ] Post the review on the PR as the bot, with a link to the gate page in our app
- [ ] Save the review and findings to the DB

### M2: Gate loop end to end

- [ ] Generate 2–3 comprehension questions from the learner's own diff and store them as a Gate
- [ ] `GET /api/gates/{id}` for Param's gate screen
- [ ] `POST /api/gates/{id}/answers`: grade each answer with Claude (score 0–100, explanation, next hint). The gate passes when every question's latest score is ≥ 70. A fail moves up the hint ladder, it doesn't approve
- [ ] On a pass: approve the PR through the GitHub API, set `Gate.status = passed` and `Submission.status = approved`, mark fixed findings `resolved`, then call Param's `progress.record_gate_pass(...)`. Leave `passed_at` to it
- [ ] Run the full loop live 3+ times. Record a backup video of it

### M3: Transparency + hardening

- [ ] Return the "why" with every grade and finding. Add `POST /api/reviews/{id}/flag`
- [ ] Timeouts and retries on Claude and GitHub calls. Handle `stop_reason == "refusal"`
- [x] Cached fallback tickets for the calculator: `generate_tickets` returns them with `is_fallback=True` when Claude fails, with a 25s timeout and one SDK retry. The expression ticket comes first, matching the demo PR
- [ ] Cached review and questions for the demo PR, in case the API is slow or down during judging
- [ ] Agree with Param who adds `is_fallback` to the `POST /api/projects` response in `schemas.py` and, if the label should survive a reload, a column on `Project`

### M4: Polish + submit

- [ ] Security check of our own repo: no secrets in history, every endpoint validated
- [ ] Backend setup steps in the README
- [ ] Demo video and Devpost, with Param

## Blocked / need from Param

- M0: PR #2 reworked for no levels, and his OK on the no-levels contract in project-plan.md
- M2: `progress.record_gate_pass()` to call when a gate passes (in PR #2)

## Todo once PR #2 merges

`reviewer.py` is standalone so it could be built before the skeleton. When PR #2 lands:

- [ ] Ask Param to add `anthropic` to `backend/pyproject.toml` (shared file), or do it in a small PR after telling him
- [ ] Add `anthropic_api_key` to `config.Settings` and pass it to `anthropic.Anthropic(api_key=...)`. Right now the SDK reads it from the environment, which only works with `uv run --env-file .env`
- [ ] Replace the `SkillAreaName` Literal in `reviewer.py` with `models.SkillArea`
- [ ] Map `ReviewResult` onto `Review` + `Finding` rows (`hints` = `[concept, where_to_look, snippet]`) and `TicketSet` onto `Project` + `Ticket`
- [ ] Run `scripts/try_reviewer.py` with plain `uv run python -m scripts.try_reviewer` (it now takes the demo ticket from `FALLBACK_TICKETS`, since there's no seeded project any more)
- [ ] Add the run and test commands to the Commands section of CLAUDE.md

## Notes

- Claude: `claude-opus-5-5`. `client.messages.parse(..., output_format=Model)`, then read `response.parsed_output`.
- `reviewer.py` uses `client.beta.messages.parse` with `fallbacks="default"` (beta `server-side-fallback-2026-07-01`), so if Opus 5.5's safety classifier declines security-flavoured code, the API retries on another model in the same call.
- First runs (2026-11-07): tickets take ~15s, the review ~29s, which fits inside the 60s timeout. On the `eval()` PR it found CWE-94 at `calculator.py:32`, the `1/0` crash, other inputs that crash or slip through, and the missing tests. On `demo/evaluate-fix` it found one real issue: `_work_out` recurses once per operator, so a very long sum crashes with `RecursionError`. To keep the fix push clean in the demo, add an input-length cap to `demo/evaluate-fix`.
