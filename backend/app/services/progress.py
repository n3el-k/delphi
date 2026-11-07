"""Learner progress. Everything here is computed from the DB, never stored (plan: "computed, not stored")."""

from sqlmodel import Session, col, func, select

from app.models import (
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Learner,
    Level,
    Project,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)


def get_me(session: Session) -> Learner:
    """There is exactly one seeded learner, so every endpoint means "me"."""
    learner = session.exec(select(Learner).order_by(Learner.id)).first()
    if learner is None:
        raise LookupError("No learner seeded. Run `uv run python -m app.seed`.")
    return learner


def approved_ticket_ids(session: Session, learner_id: int) -> set[int]:
    rows = session.exec(
        select(Submission.ticket_id).where(
            Submission.learner_id == learner_id,
            Submission.status == SubmissionStatus.approved,
        )
    )
    return set(rows)


def level_projects(session: Session, level_id: int) -> list[tuple[Project, list[Ticket]]]:
    """Projects on a level in order, each with its tickets in order."""
    projects = session.exec(select(Project).where(Project.level_id == level_id).order_by(Project.id)).all()
    return [
        (p, list(session.exec(select(Ticket).where(Ticket.project_id == p.id).order_by(Ticket.id)).all()))
        for p in projects
    ]


def is_project_done(tickets: list[Ticket], approved: set[int]) -> bool:
    """A project is done once every one of its tickets has an approved PR."""
    return bool(tickets) and all(t.id in approved for t in tickets)


def security_fixes_done(session: Session, learner_id: int) -> int:
    """Security findings on this learner's PRs that they went on to fix."""
    return session.exec(
        select(func.count(col(Finding.id)))
        .join(Review, col(Finding.review_id) == col(Review.id))
        .join(Submission, col(Review.submission_id) == col(Submission.id))
        .where(
            Submission.learner_id == learner_id,
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


def current_level(session: Session, learner: Learner) -> Level:
    level = session.get(Level, learner.current_level_id)
    assert level is not None  # enforced by the foreign key
    return level
