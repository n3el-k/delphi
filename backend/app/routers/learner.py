"""Param's learner endpoints: /api/me, /api/dashboard.

These stay thin: they fetch data, call services/progress.py for the rules,
and shape the result into the response models from schemas.py.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Project, SkillArea, SkillScore, Ticket
from app.schemas import (
    DashboardOut,
    MeOut,
    ProjectIn,
    ProjectOut,
    ProjectRef,
    SkillOut,
    TicketBase,
    TicketOut,
)
from app.services import progress, reviewer

router = APIRouter(prefix="/api", tags=["learner"])

TicketGenerator = Callable[[str], reviewer.TicketResult]


def get_ticket_generator() -> TicketGenerator:
    """The function that turns an idea into tickets: Neel's Claude call.

    It's a dependency so tests can swap in a fake (app.dependency_overrides) and never call Claude.
    """
    return reviewer.generate_tickets


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
        current_project = ProjectRef(id=project.id, title=project.title, description=project.description)  # type: ignore[arg-type]
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


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectIn,
    response: Response,
    session: Session = Depends(get_session),
    generate_tickets: TicketGenerator = Depends(get_ticket_generator),
) -> ProjectOut:
    """Turn the learner's idea into a project with tickets, and save it as theirs."""
    # 1. Whose project: the current learner, the same "me" as /me and /dashboard.
    me = progress.current_learner(session)
    assert me.id is not None

    # Already made this exact project (same idea, same repo)? Return it instead of making a
    # duplicate, e.g. after a refresh. Checked before Claude, so a repeat costs nothing.
    existing = _existing_project_out(session, me.id, body)
    if existing is not None:
        response.status_code = 200  # "here it is", not "created"
        return existing

    # 2. Ask Claude (or the fake, in tests) for a title, a summary and the tickets.
    #    Done before writing anything, so nothing is half-saved while Claude thinks.
    #    If Claude is down, generate_tickets raises ReviewerError (once Neel removes his
    #    fallback): tell the learner to try again instead of failing with a bare 500.
    try:
        result = generate_tickets(body.idea)
    except reviewer.ReviewerError:
        # "from None": the learner gets our message, not the internal error chain behind it.
        raise HTTPException(status_code=503, detail="Couldn't create tickets right now. Try again in a minute.") from None

    # 3. Save the project. flush() sends it to the database so it gets an id for the tickets.
    project = Project(
        learner_id=me.id,
        idea=body.idea,
        title=result.project_title,
        description=result.description,
        repo_full_name=body.repo_full_name,
        is_fallback=result.is_fallback,
    )
    session.add(project)
    try:
        session.flush()
    except IntegrityError:
        # Another request saved this exact project while we were waiting on Claude (a double-click).
        # The unique constraint stopped a duplicate; undo our attempt and return theirs.
        session.rollback()
        existing = _existing_project_out(session, me.id, body)
        assert existing is not None  # the constraint only fires if it exists
        response.status_code = 200
        return existing
    assert project.id is not None

    # 4. Save its tickets, numbered 1, 2, 3... in the order Claude gave them
    #    (Claude puts the core feature first, which the demo relies on).
    tickets = [
        Ticket(
            project_id=project.id,
            position=position,
            title=draft.title,
            why=draft.why,
            acceptance_criteria=draft.acceptance_criteria,
            skill_areas=draft.skill_areas,
        )
        for position, draft in enumerate(result.tickets, start=1)
    ]
    session.add_all(tickets)

    # 5. Save everything at once. If anything above failed, nothing is saved.
    session.commit()

    # 6. Send back the new project and its tickets (now with their ids), as the contract says.
    return _project_out(project, tickets)


def _existing_project_out(session: Session, learner_id: int, body: ProjectIn) -> ProjectOut | None:
    """The learner's project with this exact idea and repo, shaped for the response, or None."""
    project = session.exec(
        select(Project).where(
            Project.learner_id == learner_id,
            Project.idea == body.idea,
            Project.repo_full_name == body.repo_full_name,
        )
    ).first()
    if project is None:
        return None
    tickets = session.exec(select(Ticket).where(Ticket.project_id == project.id).order_by(col(Ticket.position))).all()
    return _project_out(project, list(tickets))


def _project_out(project: Project, tickets: list[Ticket]) -> ProjectOut:
    """Shape a saved project and its tickets into the POST /api/projects response."""
    return ProjectOut(
        id=project.id,  # type: ignore[arg-type]
        title=project.title,
        description=project.description,
        is_fallback=project.is_fallback,
        tickets=[
            TicketBase(id=t.id, title=t.title, why=t.why, acceptance_criteria=t.acceptance_criteria)  # type: ignore[arg-type]
            for t in tickets
        ],
    )
