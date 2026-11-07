# How we work

There are two of us and not much time, so the rules are short.

## Branches

- `main` should always run. Don't commit code to it directly.
- The one exception is `plans/`. Plan updates can go straight to `main` after a `git pull`. See [plans/README.md](plans/README.md).
- Make a branch for each piece of work: `feat/<thing>`, `fix/<thing>`, or `chore/<thing>`.
- Keep branches short-lived. Merge often so we don't drift apart.

## Daily loop

```bash
git checkout main && git pull
git checkout -b feat/my-thing
# ...work, commit...
git push -u origin feat/my-thing
gh pr create --fill
```

## Pull requests

- Open a PR into `main` and tag the other person.
- A quick look from the other person is enough. If they're busy and it's blocking you, merge it and tell them.
- Use **Squash and merge** to keep history clean. The branch is deleted automatically.

## Avoiding conflicts

- Say in chat what files you're about to touch.
- Pull `main` into your branch before opening a PR: `git pull origin main`.
- Never commit secrets. Put them in `.env` (already gitignored) and keep a `.env.example` with the variable names.
