"""Tests for the learner endpoints and the progress rules.

Each test gets its own fresh in-memory database with the real seed data,
then simulates what Neel's gate code would do when a learner submits and passes.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, col, create_engine, select

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
    SkillScore,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.seed import seed
from app.services import progress


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
    yield TestClient(app)
    app.dependency_overrides.clear()


def demo_tickets(session: Session) -> list[Ticket]:
    """The demo learner's 6 seeded tickets: Calculator's 3, then To-do list's 3."""
    learner = progress.current_learner(session)
    return list(
        session.exec(
            select(Ticket)
            .join(Project, col(Ticket.project_id) == col(Project.id))
            .where(Project.learner_id == learner.id)
            .order_by(col(Project.id), col(Ticket.position))
        ).all()
    )


def pass_ticket(session: Session, ticket: Ticket, score: int = 90, security_fix: bool = False) -> Submission:
    """Simulate Neel's side: an approved PR, a passed gate with one graded answer, then record_gate_pass."""
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
    question = Question(gate_id=gate.id, text="What does line 3 do?")  # type: ignore[arg-type]
    session.add(question)
    session.flush()
    session.add(Answer(question_id=question.id, text="...", score=score, passed=score >= 70, explanation="..."))  # type: ignore[arg-type]
    session.flush()
    progress.record_gate_pass(session, learner.id, sub.id)  # type: ignore[arg-type]
    return sub


def test_me(client: TestClient) -> None:
    body = client.get("/api/me").json()
    assert body == {"name": "Param Mehta", "github_login": "param-m1"}


def statuses(body: dict) -> list[str]:
    return [t["status"] for t in body["tickets"]]


def test_new_learner_dashboard(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert set(body) == {"skills", "current_project", "tickets", "open_gate_id"}  # matches the contract exactly
    assert [s["score"] for s in body["skills"]] == [0] * 7
    assert body["current_project"]["title"] == "Calculator"
    assert [t["title"] for t in body["tickets"]] == [
        "Make add() and subtract() return the right answer",
        "Handle dividing by zero",
        "Evaluate a whole expression",
    ]
    assert statuses(body) == ["todo", "todo", "todo"]
    assert body["open_gate_id"] is None


def test_passing_marks_ticket_done_and_raises_skills(client: TestClient, session: Session) -> None:
    pass_ticket(session, demo_tickets(session)[0])
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["done", "todo", "todo"]
    skills = {s["area"]: s["score"] for s in body["skills"]}
    assert skills["backend"] == 10 and skills["testing"] == 10 and skills["security"] == 0


def test_low_gate_score_does_not_count_or_earn_skills(client: TestClient, session: Session) -> None:
    pass_ticket(session, demo_tickets(session)[0], score=60)  # below MIN_GATE_SCORE (70)
    body = client.get("/api/dashboard").json()
    assert statuses(body) == ["in_review", "todo", "todo"]  # has a PR, but it doesn't count
    assert [s["score"] for s in body["skills"]] == [0] * 7


def test_ticket_is_in_review_while_its_gate_is_open(client: TestClient, session: Session) -> None:
    ticket = demo_tickets(session)[0]
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


def test_finishing_a_project_moves_to_the_next(client: TestClient, session: Session) -> None:
    calc = demo_tickets(session)[:3]
    pass_ticket(session, calc[0])
    pass_ticket(session, calc[1])
    pass_ticket(session, calc[2], security_fix=True)
    body = client.get("/api/dashboard").json()
    assert body["current_project"]["title"] == "To-do list"
    assert statuses(body) == ["todo", "todo", "todo"]
    assert {s["area"]: s["score"] for s in body["skills"]}["security"] == 15  # +10 for the ticket, +5 for the fix


def test_no_current_project_once_everything_is_done(client: TestClient, session: Session) -> None:
    for t in demo_tickets(session):
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


def test_recording_the_same_pass_twice_counts_once(session: Session) -> None:
    sub = pass_ticket(session, demo_tickets(session)[0])
    assert progress.record_gate_pass(session, 1, sub.id) is False  # type: ignore[arg-type]
    backend = session.exec(select(SkillScore).where(SkillScore.area == "backend")).one()
    assert backend.score == 10


def test_cannot_record_a_pass_for_an_unapproved_pr(session: Session) -> None:
    ticket = demo_tickets(session)[0]
    sub = Submission(
        learner_id=1, ticket_id=ticket.id, repo_full_name="x/y", pr_number=1, pr_url="u",  # type: ignore[arg-type]
        head_sha="a", diff="", status=SubmissionStatus.awaiting_gate,
    )
    session.add(sub)
    session.commit()
    with pytest.raises(progress.GatePassError):
        progress.record_gate_pass(session, 1, sub.id)  # type: ignore[arg-type]


def test_cannot_record_a_pass_for_someone_elses_pr(session: Session) -> None:
    sub = pass_ticket(session, demo_tickets(session)[0])
    other = Learner(name="Someone else", github_login="someone-else")
    session.add(other)
    session.commit()
    with pytest.raises(progress.GatePassError):
        progress.record_gate_pass(session, other.id, sub.id)  # type: ignore[arg-type]


def test_skills_never_go_above_100(session: Session) -> None:
    skill = session.exec(select(SkillScore).where(SkillScore.area == "backend")).one()
    skill.score = 95
    session.add(skill)
    session.commit()
    pass_ticket(session, demo_tickets(session)[0])
    assert skill.score == 100
