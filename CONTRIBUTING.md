# How we work

There are two of us and not much time, so the rules are short.

## Branches

- `main` should always run. Never commit or push to it directly.
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
- A quick look from the other person is enough, but every PR gets one before it merges. If they're busy, keep working on another branch.
- Use **Squash and merge** to keep history clean. The branch is deleted automatically.

## Avoiding conflicts

- Say in chat what files you're about to touch.
- Pull `main` into your branch before opening a PR: `git pull origin main`.
- Never commit secrets. Put them in `.env` (already gitignored) and keep a `.env.example` with the variable names.
