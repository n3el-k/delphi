# Hack the Change 2026

Hackathon project by Neel ([@n3el-k](https://github.com/n3el-k)) and Param ([@param-m1](https://github.com/param-m1)). Speed matters more than polish: build the smallest thing that makes the demo work.

## Team workflow

Follow the rules in CONTRIBUTING.md:

@CONTRIBUTING.md

The ones that are easy to get wrong:

- **Never credit Claude.** No `Co-Authored-By: Claude` trailers in commits and no "Generated with Claude Code" lines in PR descriptions. Commits come from whoever you're working with, nobody else.
- **Never commit code straight to `main`.** Make a `feat/`, `fix/` or `chore/` branch, push it, and open a PR with `gh pr create`. Only changes inside `plans/` may go straight to `main`, and only after a `git pull`.
- **Never commit secrets.** They go in `.env`. Add the variable name (not the value) to `.env.example`.
- Pull `main` before starting work and before opening a PR.

## Plans

The project plan is the source of truth for scope and for who owns what:

@plans/project-plan.md

- Work out who you're working with: `gh api user --jq .login` returns `n3el-k` for Neel and `param-m1` for Param. Read that person's file at the start of a session: Neel's is `plans/neel.md`, Param's is `plans/param.md`. If you can't tell who it is, ask.
- Only edit the current person's plan file, never the other person's.
- Stay inside the must-have scope. If a request is a nice-to-have while must-haves are unfinished, or is out of scope, say so before building it.
- When a task is finished, update its status in the "Who's doing what" table. When something gets decided, add it to the "Decisions" table.

## Project

Stack: not chosen yet. Once it is, record here how to install, run and test the project.
