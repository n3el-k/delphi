# Neel's plan

Working notes. Only Neel edits this file. Anything decided goes in [project-plan.md](project-plan.md).

## My area

The GitHub + AI pipeline: everything that talks to GitHub or Claude. I meet Param's half at the API contract in the project plan.

## Now

M0: Param is reworking PR #2 for the no-levels scope. Meanwhile, set up the GitHub App and the Claude key.

## Next

### M0: Skeleton + contract

- [ ] Agree `models.py`, `schemas.py` and the API contract with Param (together, first thing)
- [x] ~~FastAPI skeleton~~ Param built it in PR #2
- [ ] Create the GitHub App: pull requests read/write, contents read, subscribed to `pull_request`. Private key path and webhook secret go in `.env`
- [ ] smee.io channel forwarding to local `/webhooks/github`. Confirm a ping arrives
- [ ] Claude API key in `.env`. One test `messages.parse` call that returns a Pydantic model
- [ ] Demo practice repo: the seeded calculator project, the default demo project. Prepare a demo PR with a real flaw, e.g. `eval()` on user input (code injection)

### M1: Live review + tickets

- [ ] `POST /webhooks/github`: verify `X-Hub-Signature-256`, handle `pull_request` opened and synchronize, return 200 fast and do the work in a background task
- [ ] Fetch the PR diff and match it to the learner and ticket: `Ticket: #<id>` in the PR description, else the learner's first ticket that isn't done
- [ ] `reviewer.generate_tickets(idea)`: Claude turns a project idea into 3–5 tickets (title, why, acceptance criteria, skill areas), never the how. Param's `POST /api/projects` calls it. Fall back to the calculator's tickets if Claude fails
- [ ] Review prompt returning the `Review` model: Socratic questions, security and correctness findings (class, file, line), hint ladder, policy flags against the one fixed AI rule (the AI never writes your code)
- [ ] Don't create a second `Finding` when a later push finds the same vulnerability again, so a fix is only counted once
- [ ] Enforce "no full corrected code": a rule in the prompt, plus rejecting snippets longer than about 5 lines
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
- [ ] Cached fallback tickets for the calculator, and review and questions for the demo PR, in case the API is slow or down during judging

### M4: Polish + submit

- [ ] Security check of our own repo: no secrets in history, every endpoint validated
- [ ] Backend setup steps in the README
- [ ] Demo video and Devpost, with Param

## Blocked / need from Param

- M0: PR #2 reworked for no levels, and his OK on the no-levels contract in project-plan.md
- M2: `progress.record_gate_pass()` to call when a gate passes (in PR #2)

## Notes

- Claude: `claude-opus-5-5`. `client.messages.parse(..., output_format=Model)`, then read `response.parsed_output`.
