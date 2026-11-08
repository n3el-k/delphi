"""Param's learner endpoints: /api/me, /api/dashboard.

These stay thin: they fetch data, call services/progress.py for the rules,
and shape the result into the response models from schemas.py.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import SkillArea, SkillScore
from app.schemas import DashboardOut, MeOut, ProjectRef, SkillOut, TicketOut
from app.services import progress

router = APIRouter(prefix="/api", tags=["learner"])


@router.get("/me")
def get_me(session: Session = Depends(get_session)) -> MeOut:
    me = progress.current_learner(session)
    return MeOut(
        name=me.name,
        github_login=me.github_login,
    )


@router.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)) -> DashboardOut:
    me = progress.current_learner(session)
    assert me.id is not None
    counted = progress.counted_ticket_ids(session, me.id)
    submitted = progress.submitted_ticket_ids(session, me.id)

    # The current project is the learner's newest one that isn't done yet, so a project
    # they just created shows up straight away. learner_projects() is oldest first,
    # so walk it backwards.
    current = next(
        (
            (p, t)
            for p, t in reversed(progress.learner_projects(session, me.id))
            if not progress.is_project_done(t, counted)
        ),
        None,
    )
    current_project = None
    tickets: list[TicketOut] = []
    if current is not None:
        project, project_tickets = current
        current_project = ProjectRef(id=project.id, title=project.title)  # type: ignore[arg-type]
        tickets = [
            TicketOut(
                id=t.id,  # type: ignore[arg-type]
                title=t.title,
                why=t.why,
                acceptance_criteria=t.acceptance_criteria,
                status=progress.ticket_status(t.id, counted, submitted),  # type: ignore[arg-type]
            )
            for t in project_tickets
        ]

    scores = {
        s.area: s.score for s in session.exec(select(SkillScore).where(SkillScore.learner_id == me.id)).all()
    }

    return DashboardOut(
        # Always all 7 areas, in a fixed order, so the skill map never jumps around
        skills=[SkillOut(area=area, score=scores.get(area, 0)) for area in SkillArea],
        current_project=current_project,
        tickets=tickets,
        open_gate_id=progress.open_gate_id(session, me.id),
    )
