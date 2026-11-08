"""GET /api/portfolio: the learner's experience report, for employers.

Everything here is computed from approved PRs, never typed in, so it can't claim more than
the learner actually did. It lives in its own file instead of learner.py so it can be built
while Param works in learner.py.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import (
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Project,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.schemas import PortfolioEntry, PortfolioLearner, PortfolioOut, SecurityFixOut
from app.services import progress

router = APIRouter(prefix="/api", tags=["learner"])


@router.get("/portfolio")
def get_portfolio(session: Session = Depends(get_session)) -> PortfolioOut:
    me = progress.current_learner(session)

    # A PR shows up once its gate is passed and recorded (record_gate_pass stamps passed_at).
    approved = session.exec(
        select(Submission, Gate, Ticket, Project)
        .join(Gate, col(Gate.submission_id) == col(Submission.id))
        .join(Ticket, col(Ticket.id) == col(Submission.ticket_id))
        .join(Project, col(Project.id) == col(Ticket.project_id))
        .where(
            Submission.learner_id == me.id,
            Submission.status == SubmissionStatus.approved,
            Gate.status == GateStatus.passed,
            col(Gate.passed_at).is_not(None),
        )
        .order_by(col(Gate.passed_at).desc())
    ).all()

    # Fixed security findings on those PRs. The gate code marks only the newest copy of each
    # problem resolved, so a bug reported on two pushes shows up as one fix.
    fixes = session.exec(
        select(Finding, Submission)
        .join(Review, col(Finding.review_id) == col(Review.id))
        .join(Submission, col(Review.submission_id) == col(Submission.id))
        .where(
            Submission.learner_id == me.id,
            Submission.status == SubmissionStatus.approved,
            Finding.kind == FindingKind.security,
            col(Finding.resolved).is_(True),
        )
        .order_by(col(Finding.id).desc())
    ).all()

    return PortfolioOut(
        learner=PortfolioLearner(name=me.name, github_login=me.github_login),
        projects=[
            PortfolioEntry(
                title=f"{project.title}: {ticket.title}",
                pr_url=submission.pr_url,
                approved_at=gate.passed_at,  # type: ignore[arg-type]  (filtered to not None above)
                concepts=[str(area) for area in ticket.skill_areas],
            )
            for submission, gate, ticket, project in approved
        ],
        security_fixes=[
            SecurityFixOut(
                vuln_class=finding.vuln_class or "Security issue",
                file=finding.file,
                pr_url=submission.pr_url,
                explanation=finding.explanation,
            )
            for finding, submission in fixes
        ],
    )
