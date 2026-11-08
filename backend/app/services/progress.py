"""Learner progress: which tickets count and how skills grow.

Progress is computed from the PR history every time, never stored as a number,
so it can't drift out of sync with what actually happened.
"""

from datetime import UTC, datetime

from typing import Literal

from sqlmodel import Session, col, func, select

from app.config import settings
from app.models import (
    Answer,
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Learner,
    Project,
    Question,
    Review,
    SkillScore,
    Submission,
    SubmissionStatus,
    Ticket,
)

SKILL_POINTS_PER_PASS = 10  # each skill area on the ticket
SKILL_POINTS_PER_SECURITY_FIX = 5  # extra security points per fixed security finding
MAX_SKILL = 100
MIN_GATE_SCORE = 70  # a ticket only counts when its gate score (0–100) is at least this


class NotSeededError(Exception):
    """The database has no learner yet."""


class GatePassError(ValueError):
    """record_gate_pass was called for a submission that hasn't really passed."""


# --- Who "me" is ---


def current_learner(session: Session) -> Learner:
    """The one place that decides who the current learner is.

    For now it's the demo learner named in settings. Adding GitHub sign-in later only changes this function.
    """
    login = settings.demo_learner_github_login
    learner = session.exec(select(Learner).where(Learner.github_login == login)).first()
    if learner is None:
        raise NotSeededError(f"No learner with GitHub login {login!r}. Run `uv run python -m app.seed`.")
    return learner


# --- What counts ---


def gate_score(session: Session, gate_id: int) -> float | None:
    """The lowest latest-answer score on the gate's latest push. None if a question is unanswered.

    Only the latest push counts: each push gets its own questions (`Question.review_id`), and
    the learner answers the ones about the code they're actually merging. The minimum, not the
    average, because the pass rule is "every question at least 70": one strong answer mustn't
    carry a weak one. Questions saved without a review_id (older data) all count together.
    """
    questions = list(session.exec(select(Question).where(Question.gate_id == gate_id)).all())
    latest_push = max((q.review_id for q in questions if q.review_id is not None), default=None)
    if latest_push is not None:
        questions = [q for q in questions if q.review_id == latest_push]
    if not questions:
        return None
    latest_scores = []
    for q in questions:
        latest = session.exec(
            select(Answer).where(Answer.question_id == q.id).order_by(col(Answer.id).desc())
        ).first()
        if latest is None:
            return None
        latest_scores.append(latest.score)
    return min(latest_scores)


def counted_ticket_ids(session: Session, learner_id: int) -> set[int]:
    """Tickets whose PR was approved with a gate score of at least MIN_GATE_SCORE."""
    rows = session.exec(
        select(Submission.ticket_id, Gate.id)
        .join(Gate, col(Gate.submission_id) == col(Submission.id))
        .where(
            Submission.learner_id == learner_id,
            Submission.status == SubmissionStatus.approved,
            Gate.status == GateStatus.passed,
        )
    ).all()
    counted = set()
    for ticket_id, gate_id in rows:
        score = gate_score(session, gate_id)  # type: ignore[arg-type]
        if score is not None and score >= MIN_GATE_SCORE:
            counted.add(ticket_id)
    return counted


def is_project_done(tickets: list[Ticket], counted: set[int]) -> bool:
    """A project is done once every one of its tickets counts."""
    return bool(tickets) and all(t.id in counted for t in tickets)


def learner_projects(session: Session, learner_id: int) -> list[tuple[Project, list[Ticket]]]:
    """The learner's projects, oldest first, each with its tickets in order."""
    projects = session.exec(
        select(Project).where(Project.learner_id == learner_id).order_by(col(Project.id))
    ).all()
    return [
        (p, list(session.exec(select(Ticket).where(Ticket.project_id == p.id).order_by(col(Ticket.position))).all()))
        for p in projects
    ]


def submitted_ticket_ids(session: Session, learner_id: int) -> set[int]:
    """Tickets the learner has opened at least one PR for."""
    return set(session.exec(select(Submission.ticket_id).where(Submission.learner_id == learner_id)).all())


TicketStatus = Literal["todo", "in_review", "done"]


def ticket_status(ticket_id: int, counted: set[int], submitted: set[int]) -> TicketStatus:
    """done = counts (approved, gate passed, score ≥ 70); in_review = has a PR that doesn't count yet."""
    if ticket_id in counted:
        return "done"
    if ticket_id in submitted:
        return "in_review"
    return "todo"


def open_gate_id(session: Session, learner_id: int) -> int | None:
    """The learner's most recent gate that hasn't been passed yet."""
    return session.exec(
        select(Gate.id)
        .join(Submission, col(Gate.submission_id) == col(Submission.id))
        .where(Submission.learner_id == learner_id, Gate.status != GateStatus.passed)
        .order_by(col(Gate.id).desc())
    ).first()


# --- What happens when you pass ---


def record_gate_pass(session: Session, learner_id: int, submission_id: int) -> bool:
    """Called by Neel's gate code right after a gate passes and the PR is approved.

    Raises skill scores for the ticket's areas (only if the gate score is at least
    MIN_GATE_SCORE), then commits the session.

    Safe to call more than once: it stamps `Gate.passed_at`, and if that's already set it
    does nothing and returns False. So the gate code should set `Gate.status = passed`
    but leave `passed_at` to this function.
    """
    submission = session.get(Submission, submission_id)
    learner = session.get(Learner, learner_id)
    if submission is None or learner is None:
        raise GatePassError("Unknown learner or submission")
    if submission.learner_id != learner_id:
        raise GatePassError("That submission belongs to a different learner")
    if submission.status != SubmissionStatus.approved:
        raise GatePassError("The PR isn't approved yet")
    gate = session.exec(select(Gate).where(Gate.submission_id == submission_id)).first()
    if gate is None or gate.status != GateStatus.passed:
        raise GatePassError("The gate hasn't been passed")
    if gate.passed_at is not None:
        return False  # already recorded: never award the same pass twice

    gate.passed_at = datetime.now(UTC)
    session.add(gate)
    ticket = session.get(Ticket, submission.ticket_id)
    assert ticket is not None  # guaranteed by the foreign key

    assert gate.id is not None
    score = gate_score(session, gate.id)
    if score is None or score < MIN_GATE_SCORE:
        session.commit()  # the pass is recorded, but a low score earns no skill points
        return True

    fixes = session.exec(
        select(func.count(col(Finding.id)))
        .join(Review, col(Finding.review_id) == col(Review.id))
        .where(
            Review.submission_id == submission_id,
            Finding.kind == FindingKind.security,
            col(Finding.resolved).is_(True),
        )
    ).one()

    gains = {area: SKILL_POINTS_PER_PASS for area in ticket.skill_areas}
    if fixes:
        gains["security"] = gains.get("security", 0) + fixes * SKILL_POINTS_PER_SECURITY_FIX
    for area, points in gains.items():
        skill = session.exec(
            select(SkillScore).where(SkillScore.learner_id == learner_id, SkillScore.area == area)
        ).first()
        if skill is None:
            skill = SkillScore(learner_id=learner_id, area=area, score=0)
        skill.score = min(MAX_SKILL, skill.score + points)
        session.add(skill)

    session.commit()
    return True
