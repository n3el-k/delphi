"""Tests for the learner endpoints and the progress rules.

Each test gets its own fresh in-memory database with the real seed data,
then simulates what Neel's gate code would do when a learner submits and passes.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

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


def level1_tickets(session: Session) -> list[Ticket]:
    return list(
        session.exec(
            select(Ticket).join(Project).where(Project.level_id == 1).order_by(Project.position, Ticket.position)
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
    assert body["github_login"] == "param-m1"
    assert body["current_level"] == {"number": 1, "name": "Foundations"}


def test_levels_show_the_ramp(client: TestClient) -> None:
    levels = client.get("/api/levels").json()
    assert [lv["status"] for lv in levels] == ["current", "locked", "locked", "locked"]
    assert [(lv["starts_at"], lv["ends_at"]) for lv in levels] == [
        ("snippet", "function"), ("function", "file"), ("file", "delegated"), ("delegated", "system"),
    ]
    assert levels[0]["requirements"] == {"projects": 2, "min_gate_score": 70, "security_fixes": 1}


def test_new_learner_dashboard(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert [s["score"] for s in body["skills"]] == [0] * 7
    assert body["current_project"]["title"] == "Calculator"
    assert body["current_ticket"]["size"] == "snippet"
    assert body["current_ticket"]["title"] == "Make add() and subtract() return the right answer"
    assert body["open_gate_id"] is None
    assert body["progress"] == {"projects": {"done": 0, "required": 2}, "security_fixes": {"done": 0, "required": 1}}


def test_passing_moves_to_next_ticket_and_raises_skills(client: TestClient, session: Session) -> None:
    first = level1_tickets(session)[0]
    pass_ticket(session, first)
    body = client.get("/api/dashboard").json()
    assert body["current_ticket"]["title"] == "Handle dividing by zero"
    skills = {s["area"]: s["score"] for s in body["skills"]}
    assert skills["backend"] == 10 and skills["testing"] == 10 and skills["security"] == 0


def test_low_gate_score_does_not_count(client: TestClient, session: Session) -> None:
    first = level1_tickets(session)[0]
    pass_ticket(session, first, score=60)  # below Level 1's minimum of 70
    body = client.get("/api/dashboard").json()
    assert body["current_ticket"]["title"] == first.title


def test_security_fix_counts(client: TestClient, session: Session) -> None:
    calc = level1_tickets(session)[:3]
    for t in calc[:2]:
        pass_ticket(session, t)
    pass_ticket(session, calc[2], security_fix=True)
    body = client.get("/api/dashboard").json()
    assert body["progress"] == {"projects": {"done": 1, "required": 2}, "security_fixes": {"done": 1, "required": 1}}
    assert body["current_project"]["title"] == "To-do list"
    assert {s["area"]: s["score"] for s in body["skills"]}["security"] == 15  # +10 for the ticket, +5 for the fix


def test_finishing_level_1_promotes_to_level_2(client: TestClient, session: Session) -> None:
    for i, t in enumerate(level1_tickets(session)):
        pass_ticket(session, t, security_fix=(i == 2))
    assert client.get("/api/me").json()["current_level"]["number"] == 2
    levels = client.get("/api/levels").json()
    assert [lv["status"] for lv in levels] == ["done", "current", "locked", "locked"]
    # Level 2 has no content yet, so there's no current project
    body = client.get("/api/dashboard").json()
    assert body["current_project"] is None and body["current_ticket"] is None
    assert body["progress"]["projects"] == {"done": 0, "required": 2}


def test_no_promotion_without_a_security_fix(session: Session) -> None:
    for t in level1_tickets(session):
        pass_ticket(session, t)
    learner = session.exec(select(Learner)).one()
    assert learner.current_level_id == 1
