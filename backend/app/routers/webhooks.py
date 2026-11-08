"""POST /webhooks/github: where the live GitHub loop starts.

The request itself only does fast, local work: check the signature, match the PR to a
project and ticket, and create the Submission and its Gate. It returns 202 straight away,
so GitHub doesn't time out (it waits 10s) and the gate link in the bot's comment works
before the review is done. The slow part (diff, Claude review, bot comment) runs after
the response in a background task.
"""

import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.config import settings
from app.db import get_session
from app.models import (
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Project,
    Question,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.services import github, progress, reviewer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

# opened: a new PR. synchronize: a new push to it. reopened: a closed PR is back.
HANDLED_ACTIONS = {"opened", "reopened", "synchronize"}
TICKET_REF = re.compile(r"Ticket:\s*#(\d+)", re.IGNORECASE)
# Keeps one huge PR from blowing the Claude call's size and cost. Learner PRs are small.
MAX_DIFF_CHARS = 60_000


# --- The parts of GitHub's pull_request payload we use ---------------------------
# Pydantic ignores every other field, so we only depend on what we read.


class _Head(BaseModel):
    sha: str


class _PullRequest(BaseModel):
    number: int
    html_url: str
    body: str | None = None
    head: _Head


class _Repository(BaseModel):
    full_name: str


class PullRequestEvent(BaseModel):
    action: str
    pull_request: _PullRequest
    repository: _Repository


# --- The endpoint --------------------------------------------------------------


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    response: Response,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    # The body is read raw rather than as a Pydantic parameter, because the signature
    # covers the exact bytes. It's still validated with a Pydantic model, just after the check.
    body = await request.body()
    if not github.signature_is_valid(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event == "ping":
        response.status_code = 200
        return {"status": "pong"}
    if x_github_event != "pull_request":
        return {"status": "ignored"}

    try:
        event = PullRequestEvent.model_validate_json(body)
    except ValidationError:
        raise HTTPException(status_code=422, detail="Unexpected pull_request payload") from None
    if event.action not in HANDLED_ACTIONS:
        return {"status": "ignored"}

    submission = register_submission(session, event)
    if submission is None:
        return {"status": "ignored"}

    # The background task gets the engine, not this request's session, which closes
    # when the response is sent. Taking it from the session means tests' in-memory DB works too.
    background.add_task(review_submission, session.get_bind(), submission.id, submission.head_sha)
    return {"status": "reviewing"}


# --- Matching a PR to a project, ticket and gate -------------------------------


def register_submission(session: Session, event: PullRequestEvent) -> Submission | None:
    """Create or update the Submission and Gate for this PR. None if it isn't ours to review."""
    pr, repo = event.pull_request, event.repository.full_name

    # The repo is what links a PR to a learner: they linked it when they created the project.
    # The newest project wins if they linked the same repo twice.
    project = session.exec(
        select(Project)
        .where(func.lower(Project.repo_full_name) == repo.lower())
        .order_by(col(Project.id).desc())
    ).first()
    if project is None:
        logger.info("Ignoring PR %s#%s: no project is linked to that repo", repo, pr.number)
        return None

    submission = session.exec(
        select(Submission).where(Submission.repo_full_name == repo, Submission.pr_number == pr.number)
    ).first()
    if submission is not None and submission.status == SubmissionStatus.approved:
        return None  # already approved: a later push doesn't reopen the gate
    if submission is not None and submission.head_sha == pr.head.sha:
        # The same push again: GitHub redelivering, or two tunnels forwarding one event.
        # Only `reopened` gets another try, and only if this push was never reviewed
        # (its review failed), so a learner can retry without pushing a dummy commit.
        if event.action != "reopened" or _has_review(session, submission.id, pr.head.sha):  # type: ignore[arg-type]
            logger.info("Ignoring a repeat delivery for %s#%s at %s", repo, pr.number, pr.head.sha[:7])
            return None

    if submission is None:
        ticket = pick_ticket(session, project, pr.body)
        if ticket is None:
            logger.info("Ignoring PR %s#%s: the project has no tickets", repo, pr.number)
            return None
        submission = Submission(
            learner_id=project.learner_id,
            ticket_id=ticket.id,  # type: ignore[arg-type]
            repo_full_name=repo,
            pr_number=pr.number,
            pr_url=pr.html_url,
            head_sha=pr.head.sha,
            diff="",  # filled in by the background task
        )
    else:
        # A new push: review the new head. The ticket stays the one the PR started with.
        submission.head_sha = pr.head.sha
        submission.status = SubmissionStatus.reviewing
    session.add(submission)
    try:
        session.flush()
    except IntegrityError:
        # GitHub sometimes delivers the same event twice at once. The other request won.
        session.rollback()
        return None

    gate = session.exec(select(Gate).where(Gate.submission_id == submission.id)).first()
    if gate is None:
        gate = Gate(submission_id=submission.id)  # type: ignore[arg-type]
    gate.status = GateStatus.reviewing
    session.add(gate)
    session.commit()
    session.refresh(submission)
    return submission


def _has_review(session: Session, submission_id: int, head_sha: str) -> bool:
    return session.exec(
        select(Review.id).where(Review.submission_id == submission_id, Review.head_sha == head_sha)
    ).first() is not None


def pick_ticket(session: Session, project: Project, pr_body: str | None) -> Ticket | None:
    """`Ticket: #<id>` in the PR description if it's one of this project's tickets,
    else the first ticket that isn't done (the core ticket comes first)."""
    tickets = session.exec(
        select(Ticket).where(Ticket.project_id == project.id).order_by(col(Ticket.position))
    ).all()
    if not tickets:
        return None
    match = TICKET_REF.search(pr_body or "")
    if match:
        named = next((t for t in tickets if t.id == int(match.group(1))), None)
        if named is not None:
            return named
    done = progress.counted_ticket_ids(session, project.learner_id)
    return next((t for t in tickets if t.id not in done), tickets[0])


# --- The background review -----------------------------------------------------


def review_submission(engine: Engine, submission_id: int, head_sha: str) -> None:
    """Fetch the diff, review it with Claude, save the review, post it on the PR, open the gate.

    On a failure the gate stays in `reviewing` and the error is logged. A new push retries.
    """
    with Session(engine) as session:
        submission = session.get(Submission, submission_id)
        assert submission is not None
        ticket = session.get(Ticket, submission.ticket_id)
        assert ticket is not None

        try:
            diff = github.get_pr_diff(submission.repo_full_name, submission.pr_number)
        except github.GitHubError as e:
            logger.error("Couldn't fetch the diff for submission %s: %s", submission_id, e)
            return
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n[diff cut off: too long to review in full]\n"

        context = reviewer.TicketContext(title=ticket.title, why=ticket.why, acceptance_criteria=ticket.acceptance_criteria)
        try:
            result = reviewer.review_diff(diff, context, previous_findings(session, submission_id))
        except reviewer.ReviewerError as e:
            logger.error("Review failed for submission %s: %s", submission_id, e)
            return

        # A newer push may have landed while Claude was working. Its own task will review it,
        # so this older review would only confuse the learner.
        session.refresh(submission)
        if submission.head_sha != head_sha:
            logger.info("Dropping the review of %s for submission %s: a newer push arrived", head_sha, submission_id)
            return
        # Last check against two tasks for the same push racing each other.
        if _has_review(session, submission_id, head_sha):
            logger.info("Dropping a second review of %s for submission %s", head_sha, submission_id)
            return

        review = Review(
            submission_id=submission_id,
            head_sha=head_sha,
            summary=result.summary,
            policy_flags=result.policy_flags,
        )
        session.add(review)
        session.flush()
        findings = [
            Finding(
                review_id=review.id,  # type: ignore[arg-type]
                kind=FindingKind(f.kind),
                vuln_class=f.vuln_class,
                file=f.file,
                line=f.line,
                explanation=f.explanation,
                socratic_question=f.socratic_question,
                hints=[f.hints.concept, f.hints.where_to_look, f.hints.snippet],
                # The bot's comment shows the concept hint, so it counts as revealed.
                hints_revealed=1,
            )
            for f in result.findings
        ]
        session.add_all(findings)
        session.flush()  # gives the findings ids, so questions can point at them

        gate = session.exec(select(Gate).where(Gate.submission_id == submission_id)).one()
        session.add_all(
            Question(
                gate_id=gate.id,  # type: ignore[arg-type]
                review_id=review.id,
                finding_id=findings[q.finding_index].id if q.finding_index is not None else None,
                text=q.text,
                file=q.file,
                line=q.line,
            )
            for q in result.questions
        )

        submission.diff = diff
        submission.status = SubmissionStatus.awaiting_gate
        gate.status = GateStatus.open
        session.add_all([submission, gate])
        # Saved before posting, so the gate page works even if GitHub is slow to take the comment.
        session.commit()

        try:
            review.github_comment_id = github.post_comment(
                submission.repo_full_name, submission.pr_number, format_comment(result, findings, gate.id)  # type: ignore[arg-type]
            )
        except github.GitHubError as e:
            logger.error("Couldn't post the review for submission %s: %s", submission_id, e)
            return
        session.add(review)
        session.commit()


def previous_findings(session: Session, submission_id: int) -> list[reviewer.PreviousFinding]:
    """The findings of this PR's latest review, so the next review can see what got fixed."""
    last = session.exec(
        select(Review).where(Review.submission_id == submission_id).order_by(col(Review.id).desc())
    ).first()
    if last is None:
        return []
    rows = session.exec(select(Finding).where(Finding.review_id == last.id).order_by(col(Finding.id))).all()
    return [
        reviewer.PreviousFinding(kind=f.kind, vuln_class=f.vuln_class, file=f.file, line=f.line, explanation=f.explanation)
        for f in rows
    ]


def format_comment(result: reviewer.ReviewResult, findings: list[Finding], gate_id: int) -> str:
    """The bot's PR comment. Only the first hint rung: the rest unlock in the app,
    and the snippet is never posted on GitHub."""
    lines = ["### Senior review", "", result.summary, ""]
    for n, f in enumerate(findings, start=1):
        label = f.vuln_class or ("Security" if f.kind == FindingKind.security else "Correctness")
        where = f"`{f.file}:{f.line}`" if f.line else f"`{f.file}`"
        lines += [
            f"**{n}. {label}** in {where}",
            "",
            f.explanation,
            "",
            f"> {f.socratic_question}",
            "",
            f"Hint: {f.hints[0]}",
            "",
        ]
    if result.policy_flags:
        lines += ["**Against the rules for this project:**", *(f"- {flag}" for flag in result.policy_flags), ""]
    gate_url = f"{settings.frontend_origin.rstrip('/')}/gates/{gate_id}"
    if any(f.kind == FindingKind.security for f in findings):
        next_step = (
            "Fix the security issue above and push again. Then answer a few questions about "
            f"your own code to get this PR approved: [open your review]({gate_url})."
        )
    else:
        next_step = f"Before this PR can be approved, answer a few questions about your own code: [open your review]({gate_url})."
    lines += ["---", next_step, "More hints unlock there as you go."]
    return "\n".join(lines)
