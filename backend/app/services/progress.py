"""Learner progress: what counts, how skills grow, and when you level up.

Progress is computed from the PR history every time, never stored as a number,
so it can't drift out of sync with what actually happened.
"""

from datetime import UTC, datetime

from sqlmodel import Session, col, func, select

from app.models import (
    Answer,
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Learner,
    Level,
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


class NotSeededError(Exception):
    """The database has no learner yet."""


class GatePassError(ValueError):
    """record_gate_pass was called for a submission that hasn't really passed."""


# --- Who "me" is ---


def current_learner(session: Session) -> Learner:
    """The one place that decides who the current learner is.

    For now there's a single seeded learner. Adding GitHub sign-in later only changes this function.
    """
    learner = session.exec(select(Learner).order_by(col(Learner.id))).first()
    if learner is None:
        raise NotSeededError("No learner seeded. Run `uv run python -m app.seed`.")
    return learner


def current_level(session: Session, learner: Learner) -> Level:
    level = session.get(Level, learner.current_level_id)
    assert level is not None  # guaranteed by the foreign key
    return level


# --- What counts ---


def gate_score(session: Session, gate_id: int) -> float | None:
    """Average of the latest answer's score on each question. None if a question is unanswered."""
    questions = session.exec(select(Question).where(Question.gate_id == gate_id)).all()
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
    return sum(latest_scores) / len(latest_scores)


def counted_ticket_ids(session: Session, learner_id: int, level: Level) -> set[int]:
    """Tickets on this level whose PR was approved with a gate score at or above the level minimum."""
    rows = session.exec(
        select(Submission.ticket_id, Gate.id)
        .join(Gate, col(Gate.submission_id) == col(Submission.id))
        .join(Ticket, col(Submission.ticket_id) == col(Ticket.id))
        .join(Project, col(Ticket.project_id) == col(Project.id))
        .where(
            Submission.learner_id == learner_id,
            Submission.status == SubmissionStatus.approved,
            Gate.status == GateStatus.passed,
            Project.level_id == level.id,
        )
    ).all()
    counted = set()
    for ticket_id, gate_id in rows:
        score = gate_score(session, gate_id)  # type: ignore[arg-type]
        if score is not None and score >= level.min_gate_score:
            counted.add(ticket_id)
    return counted


def level_projects(session: Session, level_id: int) -> list[tuple[Project, list[Ticket]]]:
    """A level's projects in order, each with its tickets in order."""
    projects = session.exec(
        select(Project).where(Project.level_id == level_id).order_by(col(Project.position))
    ).all()
    return [
        (
            p,
            list(session.exec(select(Ticket).where(Ticket.project_id == p.id).order_by(col(Ticket.position))).all()),
        )
        for p in projects
    ]


def is_project_done(tickets: list[Ticket], counted: set[int]) -> bool:
    """A project is done once every one of its tickets counts."""
    return bool(tickets) and all(t.id in counted for t in tickets)


def projects_done(session: Session, learner_id: int, level: Level) -> int:
    assert level.id is not None
    counted = counted_ticket_ids(session, learner_id, level)
    return sum(is_project_done(tickets, counted) for _, tickets in level_projects(session, level.id))


def security_fixes_done(session: Session, learner_id: int, level: Level) -> int:
    """Security findings on this learner's approved PRs for this level that they fixed."""
    return session.exec(
        select(func.count(col(Finding.id)))
        .join(Review, col(Finding.review_id) == col(Review.id))
        .join(Submission, col(Review.submission_id) == col(Submission.id))
        .join(Ticket, col(Submission.ticket_id) == col(Ticket.id))
        .join(Project, col(Ticket.project_id) == col(Project.id))
        .where(
            Submission.learner_id == learner_id,
            Submission.status == SubmissionStatus.approved,
            Project.level_id == level.id,
            Finding.kind == FindingKind.security,
            col(Finding.resolved).is_(True),
        )
    ).one()


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

    Raises skill scores for the ticket's areas, then promotes the learner if the level's
    requirements are now met. Commits the session.

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

    session.flush()
    maybe_promote(session, learner)
    session.commit()
    return True


def maybe_promote(session: Session, learner: Learner) -> bool:
    """Move the learner up a level if they've met every requirement of their current one."""
    assert learner.id is not None
    level = current_level(session, learner)
    met = (
        projects_done(session, learner.id, level) >= level.required_projects
        and security_fixes_done(session, learner.id, level) >= level.required_security_fixes
    )
    next_level = session.exec(select(Level).where(Level.number == level.number + 1)).first()
    if not met or next_level is None:
        return False
    learner.current_level_id = next_level.id  # type: ignore[assignment]
    session.add(learner)
    return True
