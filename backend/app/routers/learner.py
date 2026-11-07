"""Param's learner endpoints: /api/me, /api/levels, /api/dashboard."""

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import Level, SkillScore
from app.schemas import (
    Count,
    DashboardOut,
    LevelOut,
    LevelRef,
    LevelRequirements,
    MeOut,
    ProgressOut,
    ProjectRef,
    SkillOut,
    TicketOut,
)
from app.services import progress

router = APIRouter(prefix="/api", tags=["learner"])


@router.get("/me")
def get_me(session: Session = Depends(get_session)) -> MeOut:
    me = progress.get_me(session)
    level = progress.current_level(session, me)
    return MeOut(
        name=me.name,
        github_login=me.github_login,
        current_level=LevelRef(number=level.number, name=level.name),
    )


@router.get("/levels")
def get_levels(session: Session = Depends(get_session)) -> list[LevelOut]:
    me = progress.get_me(session)
    current = progress.current_level(session, me).number
    levels = session.exec(select(Level).order_by(Level.number)).all()
    return [
        LevelOut(
            number=lv.number,
            name=lv.name,
            ai_policy=lv.ai_policy,
            unlocks=lv.unlocks,
            requirements=LevelRequirements(
                projects=lv.required_projects,
                min_gate_score=lv.min_gate_score,
                security_fixes=lv.required_security_fixes,
            ),
            status="done" if lv.number < current else "current" if lv.number == current else "locked",
        )
        for lv in levels
    ]


@router.get("/dashboard")
def get_dashboard(session: Session = Depends(get_session)) -> DashboardOut:
    me = progress.get_me(session)
    assert me.id is not None
    level = progress.current_level(session, me)
    approved = progress.approved_ticket_ids(session, me.id)
    projects = progress.level_projects(session, me.current_level_id)

    current_project = current_ticket = None
    for project, tickets in projects:
        if not progress.is_project_done(tickets, approved):
            current_project = ProjectRef(id=project.id, title=project.title)  # type: ignore[arg-type]
            ticket = next((t for t in tickets if t.id not in approved), None)
            if ticket is not None:
                current_ticket = TicketOut(
                    id=ticket.id,  # type: ignore[arg-type]
                    title=ticket.title,
                    why=ticket.why,
                    acceptance_criteria=ticket.acceptance_criteria,
                )
            break

    scores = session.exec(select(SkillScore).where(SkillScore.learner_id == me.id)).all()
    by_area = {s.area: s.score for s in scores}

    return DashboardOut(
        skills=[SkillOut(area=a, score=s) for a, s in by_area.items()],
        current_project=current_project,
        current_ticket=current_ticket,
        open_gate_id=progress.open_gate_id(session, me.id),
        progress=ProgressOut(
            projects=Count(
                done=sum(progress.is_project_done(t, approved) for _, t in projects),
                required=level.required_projects,
            ),
            security_fixes=Count(
                done=progress.security_fixes_done(session, me.id),
                required=level.required_security_fixes,
            ),
        ),
    )
