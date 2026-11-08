"""Tests for the learner endpoints and the progress rules.

Each test gets its own fresh in-memory database with the real seed data (one learner,
no projects). Tests add the projects they need with add_project(), the way
POST /api/projects will, then simulate what Neel's gate code does when a learner passes.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, col, create_engine, func, select

import app.models  # noqa: F401  (registers the tables)
from app.db import get_session
from app.main import app
from app.models import (
    Answer,
    Finding,
    FindingKind,
    Gate,
    GateStatus,
    Learner,
    Project,
    Question,
    SkillArea,
    SkillScore,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.routers.learner import get_ticket_generator
from app.seed import seed
from app.services import progress
from app.services.reviewer import ReviewerError, TicketDraft, TicketResult

# What the fake ticket generator returns: a known, fixed answer instead of a live Claude call.
FAKE_TICKETS = TicketResult(
    project_title="Habit tracker",
    description="A habit tracker for students who want to build daily routines and see their streaks.",
    tickets=[
        TicketDraft(
            title="Add a habit",
            why="Nothing else works until a learner can record what they want to track.",
            acceptance_criteria=["A habit with a name can be added", "An empty name is rejected"],
            skill_areas=[SkillArea.backend, SkillArea.database],
        ),
        TicketDraft(
            title="Mark a habit done for today",
            why="Ticking a habit off is the core daily action.",
            acceptance_criteria=["Marking done twice on the same day counts once"],
            skill_areas=[SkillArea.backend, SkillArea.testing],
        ),
        TicketDraft(
            title="Show the current streak",
            why="Seeing a streak is what keeps people coming back.",
            acceptance_criteria=["The streak resets after a missed day"],
            skill_areas=[SkillArea.frontend, SkillArea.debugging],
        ),
    ],
    is_fallback=False,
)


def fake_generate_tickets(idea: str) -> TicketResult:
    """Stands in for reviewer.generate_tickets in tests: instant, free, and always the same."""
    return FAKE_TICKETS


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed(s)
        yield s


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    # Every test client uses the fake, so no test can ever call Claude by accident.
    app.dependency_overrides[get_ticket_generator] = lambda: fake_generate_tickets
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_project(session: Session, title: str = "Calculator", n_tickets: int = 3) -> list[Ticket]:
    """Give the demo learner a project with n tickets, like POST /api/projects will. Returns its tickets in order."""
    learner = progress.current_learner(session)
    project = Project(
        learner_id=learner.id, idea=f"An idea for {title}", title=title,  # type: ignore[arg-type]
        description=f"A test {title}.", repo_full_name="n3el-k/practice",
    )
    session.add(project)
    session.flush()
    tickets = [
        Ticket(
            project_id=project.id, position=i, title=f"{title} ticket {i}", why="Because.",  # type: ignore[arg-type]
            acceptance_criteria=["It works"], skill_areas=[SkillArea.backend, SkillArea.testing],
        )
        for i in range(1, n_tickets + 1)
    ]
    session.add_all(tickets)
    session.commit()
    return tickets


@pytest.fixture
def tickets(session: Session) -> list[Ticket]:
    """One project with 3 tickets, for tests that just need something to pass."""
    return add_project(session)


def pass_ticket(
    session: Session, ticket: Ticket, score: int = 90, security_fix: bool = False, other_scores: tuple[int, ...] = ()
) -> Submission:
    """Simulate Neel's side: an approved PR, a passed gate with graded answers, then record_gate_pass.

    The gate has one question scored `score`, plus one more per entry in `other_scores`.
    """
    learner = progress.current_learner(session)
    sub = Submission(
        learner_id=learner.id, ticket_id=ticket.id, repo_full_name="n3el-k/practice",  # type: ignore[arg-type]
        pr_number=ticket.id, pr_url=f"https://github.com/n3el-k/practice/pull/{ticket.id}",  # type: ignore[arg-type]
        head_sha="abc", diff="", status=SubmissionStatus.approved,
    )
    session.add(sub)
    session.flush()
    review = Review(submission_id=sub.id, head_sha="abc", summary="Looks good")  # type: ignore[arg-type]
    gate = Gate(submission_id=sub.id, status=GateStatus.passed)  # type: ignore[arg-type]
    session.add_all([review, gate])
    session.flush()
    if security_fix:
        session.add(Finding(
            review_id=review.id, kind=FindingKind.security, vuln_class="code injection",  # type: ignore[arg-type]
            file="calc.py", line=3, explanation="eval runs input as code", socratic_question="?", resolved=True,
        ))
    for i, s in enumerate((score, *other_scores), start=1):
        question = Question(gate_id=gate.id, text=f"Question {i}")  # type: ignore[arg-type]
        session.add(question)
        session.flush()
        session.add(Answer(question_id=question.id, text="...", score=s, passed=s >= 70, explanation="..."))  # type: ignore[arg-type]
    session.flush()
    progress.record_gate_pass(session, learner.id, sub.id)  # type: ignore[arg-type]
    return sub


def test_me(client: TestClient) -> None:
    body = client.get("/api/me").json()
    assert body == {"name": "Param Mehta", "github_login": "param-m1"}


def statuses(body: dict) -> list[str]:
    return [t["status"] for t in body["tickets"]]


def test_new_learner_has_an_empty_dashboard(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert set(body) == {"skills", "current_project", "tickets", "open_gate_id"}  # matches the contract exactly
    assert [s["score"] for s in body["skills"]] == [0] * 7
    assert body["current_project"] is None  # no seeded projects: the frontend shows "Start a project"
    assert body["tickets"] == []
    assert body["open_gate_id"] is None


def test_a_new_project_shows_its_tickets(client: TestClient, tickets: list[Ticket]) -> None:
    body = client.get("/api/dashboard").json()
    assert body["current_project"]["title"] == "Calculator"
    assert [t["title"] for t in body["tickets"]] == ["Calculator ticket 1", "Calculator ticket 2", "Calculator ticket 3"]
    assert statuses(body) == ["todo", "todo", "todo"]


def test_passing_marks_ticket_done_and_raises_skills(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    pass_ticket(session, tickets[0])
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["done", "todo", "todo"]
    skills = {s["area"]: s["score"] for s in body["skills"]}
    assert skills["backend"] == 10 and skills["testing"] == 10 and skills["security"] == 0


def test_low_gate_score_does_not_count_or_earn_skills(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    pass_ticket(session, tickets[0], score=60)  # below MIN_GATE_SCORE (70)
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["in_review", "todo", "todo"]  # has a PR, but it doesn't count
    assert [s["score"] for s in body["skills"]] == [0] * 7


def test_one_failed_question_stops_a_ticket_counting(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    # 90 and 55 average 72.5, which would pass on an average. Every question needs 70, so it doesn't.
    pass_ticket(session, tickets[0], score=90, other_scores=(55,))
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["in_review", "todo", "todo"]
    assert [s["score"] for s in body["skills"]] == [0] * 7


def test_ticket_is_in_review_while_its_gate_is_open(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    ticket = tickets[0]
    sub = Submission(
        learner_id=progress.current_learner(session).id, ticket_id=ticket.id,  # type: ignore[arg-type]
        repo_full_name="n3el-k/level1-calculator", pr_number=7, pr_url="https://github.com/n3el-k/level1-calculator/pull/7",
        head_sha="abc", diff="", status=SubmissionStatus.awaiting_gate,
    )
    session.add(sub)
    session.flush()
    gate = Gate(submission_id=sub.id, status=GateStatus.open)  # type: ignore[arg-type]
    session.add(gate)
    session.commit()
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["in_review", "todo", "todo"]
    assert body["open_gate_id"] == gate.id


def test_newest_unfinished_project_is_current(client: TestClient, session: Session) -> None:
    add_project(session, "Calculator")
    add_project(session, "To-do list")
    body = client.get("/api/dashboard").json()
    assert body["current_project"]["title"] == "To-do list"  # the one just created, not the older one


def test_finishing_the_newest_project_falls_back_to_an_older_one(client: TestClient, session: Session) -> None:
    add_project(session, "Calculator")
    for t in add_project(session, "To-do list"):
        pass_ticket(session, t)
    body = client.get("/api/dashboard").json()
    assert body["current_project"]["title"] == "Calculator"
    assert statuses(body) == ["todo", "todo", "todo"]


def test_a_security_fix_earns_extra_security_points(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    tickets[0].skill_areas = [SkillArea.security]
    session.add(tickets[0])
    session.commit()
    pass_ticket(session, tickets[0], security_fix=True)
    skills = {s["area"]: s["score"] for s in client.get("/api/dashboard").json()["skills"]}
    assert skills["security"] == 15  # +10 for the ticket, +5 for the fix


def test_no_current_project_once_everything_is_done(client: TestClient, session: Session, tickets: list[Ticket]) -> None:
    for t in tickets:
        pass_ticket(session, t)
    body = client.get("/api/dashboard").json()
    assert body["current_project"] is None
    assert body["tickets"] == []


def test_current_learner_is_found_by_github_login(client: TestClient, session: Session) -> None:
    me = progress.current_learner(session)
    me.github_login = "someone-else"  # the demo login no longer matches anyone
    session.add(me)
    session.commit()
    assert client.get("/api/me").status_code == 503


# --- Edge cases and safety ---


def test_empty_database_gives_a_clear_503(client: TestClient, session: Session) -> None:
    for model in (SkillScore, Learner):
        for row in session.exec(select(model)).all():
            session.delete(row)
    session.commit()
    r = client.get("/api/dashboard")
    assert r.status_code == 503
    assert r.json() == {"detail": "The app has no data yet. Run the seed script."}


def test_unexpected_errors_dont_leak_details(session: Session) -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/test-boom")
    def boom() -> dict[str, str]:
        return {}["secret_internal_key"]  # a KeyError, like a real bug would raise

    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    r = TestClient(app, raise_server_exceptions=False).get("/test-boom")
    app.dependency_overrides.clear()
    assert r.status_code == 500
    assert "secret_internal_key" not in r.text


def test_cors_only_allows_our_frontend(client: TestClient) -> None:
    ours = client.get("/api/me", headers={"Origin": "http://localhost:5173"})
    other = client.get("/api/me", headers={"Origin": "https://evil.example"})
    assert ours.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers


def test_recording_the_same_pass_twice_counts_once(session: Session, tickets: list[Ticket]) -> None:
    sub = pass_ticket(session, tickets[0])
    assert progress.record_gate_pass(session, 1, sub.id) is False  # type: ignore[arg-type]
    backend = session.exec(select(SkillScore).where(SkillScore.area == "backend")).one()
    assert backend.score == 10


def test_cannot_record_a_pass_for_an_unapproved_pr(session: Session, tickets: list[Ticket]) -> None:
    ticket = tickets[0]
    sub = Submission(
        learner_id=1, ticket_id=ticket.id, repo_full_name="x/y", pr_number=1, pr_url="u",  # type: ignore[arg-type]
        head_sha="a", diff="", status=SubmissionStatus.awaiting_gate,
    )
    session.add(sub)
    session.commit()
    with pytest.raises(progress.GatePassError):
        progress.record_gate_pass(session, 1, sub.id)  # type: ignore[arg-type]


def test_cannot_record_a_pass_for_someone_elses_pr(session: Session, tickets: list[Ticket]) -> None:
    sub = pass_ticket(session, tickets[0])
    other = Learner(name="Someone else", github_login="someone-else")
    session.add(other)
    session.commit()
    with pytest.raises(progress.GatePassError):
        progress.record_gate_pass(session, other.id, sub.id)  # type: ignore[arg-type]


def test_skills_never_go_above_100(session: Session, tickets: list[Ticket]) -> None:
    skill = session.exec(select(SkillScore).where(SkillScore.area == "backend")).one()
    skill.score = 95
    session.add(skill)
    session.commit()
    pass_ticket(session, tickets[0])
    assert skill.score == 100


# --- POST /api/projects ---

GOOD_BODY = {"idea": "A habit tracker for students", "repo_full_name": "param-m1/habits"}


def use_generator(fn) -> list[str]:  # type: ignore[no-untyped-def]
    """Swap in a different fake ticket generator for one test. Returns the ideas it was called with."""
    calls: list[str] = []

    def recording(idea: str) -> TicketResult:
        calls.append(idea)
        return fn(idea)

    app.dependency_overrides[get_ticket_generator] = lambda: recording
    return calls


def count(session: Session, model) -> int:  # type: ignore[no-untyped-def]
    return session.exec(select(func.count(col(model.id)))).one()


def test_create_project_saves_it_and_returns_201(client: TestClient, session: Session) -> None:
    r = client.post("/api/projects", json={"idea": "  A habit tracker for students  ", "repo_full_name": "param-m1/habits"})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "title", "description", "is_fallback", "tickets"}  # matches the contract exactly
    assert body["title"] == "Habit tracker"
    assert body["description"] == FAKE_TICKETS.description
    assert body["is_fallback"] is False
    assert [t["title"] for t in body["tickets"]] == ["Add a habit", "Mark a habit done for today", "Show the current streak"]
    assert all(set(t) == {"id", "title", "why", "acceptance_criteria"} for t in body["tickets"])  # no status here

    project = session.get(Project, body["id"])
    assert project is not None
    assert project.learner_id == progress.current_learner(session).id  # it's mine
    assert project.idea == "A habit tracker for students"  # trimmed
    assert project.repo_full_name == "param-m1/habits"
    tickets = session.exec(select(Ticket).where(Ticket.project_id == project.id).order_by(col(Ticket.position))).all()
    assert [t.position for t in tickets] == [1, 2, 3]
    assert tickets[0].skill_areas == [SkillArea.backend, SkillArea.database]  # copied from the draft


def test_new_project_shows_on_the_dashboard(client: TestClient) -> None:
    created = client.post("/api/projects", json=GOOD_BODY).json()
    body = client.get("/api/dashboard").json()
    assert body["current_project"] == {"id": created["id"], "title": "Habit tracker", "description": FAKE_TICKETS.description}
    assert [t["status"] for t in body["tickets"]] == ["todo", "todo", "todo"]


@pytest.mark.parametrize(
    "body",
    [
        {"idea": "", "repo_full_name": "param-m1/habits"},
        {"idea": "   ", "repo_full_name": "param-m1/habits"},
        {"idea": "x" * 1001, "repo_full_name": "param-m1/habits"},
        {"idea": "A habit tracker"},
        {"idea": "A habit tracker", "repo_full_name": "habits"},
        {"idea": "A habit tracker", "repo_full_name": "param-m1/habits/extra"},
        {"idea": "A habit tracker", "repo_full_name": "-param/habits"},
        {"idea": "A habit tracker", "repo_full_name": "https://github.com/param-m1/habits"},
        {"idea": "A habit tracker", "repo_full_name": "param-m1/.."},
    ],
)
def test_bad_input_is_rejected_before_claude(client: TestClient, session: Session, body: dict) -> None:
    calls = use_generator(lambda idea: FAKE_TICKETS)
    assert client.post("/api/projects", json=body).status_code == 422
    assert calls == []  # never asked Claude
    assert count(session, Project) == 0


def test_repeating_the_same_project_returns_it_without_calling_claude(client: TestClient, session: Session) -> None:
    calls = use_generator(lambda idea: FAKE_TICKETS)
    first = client.post("/api/projects", json=GOOD_BODY)
    again = client.post("/api/projects", json=GOOD_BODY)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert len(calls) == 1
    assert count(session, Project) == 1


def test_same_idea_with_a_different_repo_is_a_new_project(client: TestClient, session: Session) -> None:
    client.post("/api/projects", json=GOOD_BODY)
    r = client.post("/api/projects", json={**GOOD_BODY, "repo_full_name": "param-m1/habits-v2"})
    assert r.status_code == 201
    assert count(session, Project) == 2


def test_a_simultaneous_duplicate_is_caught_by_the_database(client: TestClient, session: Session) -> None:
    """A double-click: while this request waits on Claude, another one saves the same project."""
    learner_id = progress.current_learner(session).id

    def other_request_wins(idea: str) -> TicketResult:
        session.add(Project(
            learner_id=learner_id, idea=GOOD_BODY["idea"], title="Saved by the other click",  # type: ignore[arg-type]
            description="d", repo_full_name=GOOD_BODY["repo_full_name"],
        ))
        session.commit()
        return FAKE_TICKETS

    use_generator(other_request_wins)
    r = client.post("/api/projects", json=GOOD_BODY)
    assert r.status_code == 200
    assert r.json()["title"] == "Saved by the other click"  # we got theirs back
    assert count(session, Project) == 1  # and no duplicate
    assert count(session, Ticket) == 0  # our tickets were rolled back with our project


def test_claude_failing_returns_503_and_saves_nothing(client: TestClient, session: Session) -> None:
    def claude_is_down(idea: str) -> TicketResult:
        raise ReviewerError("Claude timed out")

    use_generator(claude_is_down)
    r = client.post("/api/projects", json=GOOD_BODY)
    assert r.status_code == 503
    assert r.json() == {"detail": "Couldn't create tickets right now. Try again in a minute."}
    assert "timed out" not in r.text  # the internal reason stays on the server
    assert count(session, Project) == 0


def test_fallback_tickets_are_marked_as_such(client: TestClient, session: Session) -> None:
    use_generator(lambda idea: FAKE_TICKETS.model_copy(update={"is_fallback": True}))
    body = client.post("/api/projects", json=GOOD_BODY).json()
    assert body["is_fallback"] is True
    project = session.get(Project, body["id"])
    assert project is not None and project.is_fallback is True  # survives a reload
