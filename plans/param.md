# Param's plan

Working notes. Only Param edits this file. Anything decided goes in [project-plan.md](project-plan.md).

## My area

The learner app: every screen the learner sees, plus the data and APIs behind them. I meet Neel's half at the API contract in the project plan.

## Now

M0 skeleton + M1 together on one branch, `feat/learner-app-m1`, one PR for Neel to review. Schema and API contract v1 are agreed.

## Next

### M0: Skeleton + contract

- [x] Agree `models.py`, `schemas.py` and the API contract with Neel (together, first thing)
- [ ] Vite + React + TypeScript app with Tailwind and shadcn/ui. App shell (nav, layout) and design tokens (colours, type scale, spacing)
- [ ] SQLModel tables from the agreed schema, plus `seed.py`: one learner, the 4 levels with their AI policies and what they unlock, Level 1 projects and tickets, a starting skill map
- [ ] `GET /api/me` and `GET /api/levels` returning seeded data, shown in the app with TanStack Query

### M1: Level map + dashboard

- [ ] Level map page: all 4 levels, current one active, higher ones locked, each showing what it unlocks (including AI permissions)
- [ ] Dashboard: skill map across the stack (frontend, backend, database, auth, security, git), current project and ticket, progress to the next level
- [ ] `GET /api/dashboard`

### M2: Gate screen + progress

- [ ] Gate page, linked from the bot's PR comment: review summary, findings, comprehension questions, a labelled answer field for each
- [ ] Result states: a hint on fail, a success screen on pass, plus loading and error states
- [ ] `progress.record_gate_pass()`: update skill scores and level progress (Neel's code calls this)

### M3: Full journey

- [ ] "Why you got this grade" view for each answer and finding, plus a "Flag this review" button
- [ ] Portfolio / experience report page: projects, levels, concepts shown, security fixes, links to PRs. `GET /api/portfolio`
- [ ] Nice to have: a static Level 3–4 preview and a nonprofit commissions screen for the Local Impact pitch

### M4: Polish + submit

- [ ] Accessibility pass: a keyboard-only run-through, visible focus, labels, AA contrast, axe or Lighthouse on every page
- [ ] Visual polish: empty, loading and error states, works at laptop and phone widths
- [ ] Frontend setup steps in the README
- [ ] Demo video and Devpost, with Neel

## Blocked / need from Neel

- Review of `feat/learner-app-m1` (M0 skeleton + M1). It adds the shared files `main.py`, `config.py`, `db.py`, `models.py` and `schemas.py`, copied from contract v1
- M2: the gate endpoints (`GET /api/gates/{id}`, `POST /api/gates/{id}/answers`). Mock them in the frontend until they land

## Notes

- shadcn/ui is built on Radix, so keyboard and screen reader support mostly come for free. Don't swap its components for hand-rolled divs.
