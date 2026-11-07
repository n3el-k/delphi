"""Param's learner endpoints: /api/me, /api/levels, /api/dashboard.

These stay thin: they fetch data, call services/progress.py for the rules,
and shape the result into the response models from schemas.py.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Level, SkillArea, SkillScore
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
    me = progress.current_learner(session)
    level = progress.current_level(session, me)
    return MeOut(
        name=me.name,
        github_login=me.github_login,
        current_level=LevelRef(number=level.number, name=level.name),
    )


@router.get("/levels")
def get_levels(session: Session = Depends(get_session)) -> list[LevelOut]:
    me = progress.current_learner(session)
    current = progress.current_level(session, me).number
    levels = session.exec(select(Level).order_by(col(Level.number))).all()
    return [
        LevelOut(
            number=lv.number,
            name=lv.name,
            ai_policy=lv.ai_policy,
            starts_at=lv.starts_at,
            ends_at=lv.ends_at,
            review_focus=lv.review_focus,
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
    me = progress.current_learner(session)
    assert me.id is not None
    level = progress.current_level(session, me)
    assert level.id is not None
    counted = progress.counted_ticket_ids(session, me.id, level)
    projects = progress.level_projects(session, level.id)

    # The current project is the first unfinished one; its current ticket is the first that doesn't count yet.
    current_project = current_ticket = None
    for project, tickets in projects:
        if progress.is_project_done(tickets, counted):
            continue
        current_project = ProjectRef(id=project.id, title=project.title)  # type: ignore[arg-type]
        ticket = next((t for t in tickets if t.id not in counted), None)
        if ticket is not None:
            current_ticket = TicketOut(
                id=ticket.id,  # type: ignore[arg-type]
                size=ticket.size,
                title=ticket.title,
                why=ticket.why,
                acceptance_criteria=ticket.acceptance_criteria,
            )
        break

    scores = {
        s.area: s.score for s in session.exec(select(SkillScore).where(SkillScore.learner_id == me.id)).all()
    }

    return DashboardOut(
        # Always all 7 areas, in a fixed order, so the skill map never jumps around
        skills=[SkillOut(area=area, score=scores.get(area, 0)) for area in SkillArea],
        current_project=current_project,
        current_ticket=current_ticket,
        open_gate_id=progress.open_gate_id(session, me.id),
        progress=ProgressOut(
            projects=Count(done=sum(progress.is_project_done(t, counted) for _, t in projects), required=level.required_projects),
            security_fixes=Count(
                done=progress.security_fixes_done(session, me.id, level),
                required=level.required_security_fixes,
            ),
        ),
    )
