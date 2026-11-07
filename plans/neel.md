# Neel's plan

Working notes. Only Neel edits this file. Anything decided goes in [project-plan.md](project-plan.md).

## My area

The GitHub + AI pipeline: everything that talks to GitHub or Claude. I meet Param's half at the API contract in the project plan.

## Now

M0: agree the DB schema and API contract with Param.

## Next

### M0: Skeleton + contract

- [ ] Agree `models.py`, `schemas.py` and the API contract with Param (together, first thing)
- [ ] FastAPI skeleton: `GET /health`, settings from `.env` in `config.py`, CORS for the frontend, `.env.example`
- [ ] Create the GitHub App: pull requests read/write, contents read, subscribed to `pull_request`. Private key path and webhook secret go in `.env`
- [ ] smee.io channel forwarding to local `/webhooks/github`. Confirm a ping arrives
- [ ] Claude API key in `.env`. One test `messages.parse` call that returns a Pydantic model
- [ ] Demo practice repo: the Level 1 calculator project and its ticket. Prepare a demo PR with a real flaw, e.g. `eval()` on user input (code injection)

### M1: Live review

- [ ] `POST /webhooks/github`: verify `X-Hub-Signature-256`, handle `pull_request` opened and synchronize, return 200 fast and do the work in a background task
- [ ] Fetch the PR diff and match it to the learner and ticket
- [ ] Review prompt returning the `Review` model: Socratic questions, security and correctness findings (class, file, line), hint ladder, policy flags
- [ ] Enforce "no full corrected code": a rule in the prompt, plus rejecting snippets longer than about 5 lines
- [ ] Post the review on the PR as the bot, with a link to the gate page in our app
- [ ] Save the review and findings to the DB

### M2: Gate loop end to end

- [ ] Generate 2–3 comprehension questions from the learner's own diff and store them as a Gate
- [ ] `GET /api/gates/{id}` for Param's gate screen
- [ ] `POST /api/gates/{id}/answers`: grade each answer with Claude (score, explanation, next hint). A fail moves up the hint ladder, it doesn't approve
- [ ] On a pass: approve the PR through the GitHub API and call Param's `progress.record_gate_pass(...)`
- [ ] Run the full loop live 3+ times. Record a backup video of it

### M3: Transparency + hardening

- [ ] Return the "why" with every grade and finding. Add `POST /api/reviews/{id}/flag`
- [ ] Timeouts and retries on Claude and GitHub calls. Handle `stop_reason == "refusal"`
- [ ] Cached fallback review and questions for the demo PR, in case the API is slow or down during judging

### M4: Polish + submit

- [ ] Security check of our own repo: no secrets in history, every endpoint validated
- [ ] Backend setup steps in the README
- [ ] Demo video and Devpost, with Param

## Blocked / need from Param

- M0: sign-off on the schema and API contract
- M2: `progress.record_gate_pass()` to call when a gate passes

## Notes

- Claude: `claude-opus-5-5`. `client.messages.parse(..., output_format=Model)`, then read `response.parsed_output`.
