"""Tests for GET /api/portfolio, the project summary on the dashboard, and gate_score.

The PR history is built the way the webhook leaves it, and passes go through the real
answers endpoint (with the grader and GitHub faked), so the portfolio is tested on data
produced by the actual loop.
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
    Project,
    Question,
    Review,
    SkillArea,
    SkillScore,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.seed import seed
from app.services import github, progress, reviewer


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed(s)
        yield s


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Answers containing "good" score 90, anything else 20. GitHub approval is a no-op.
    monkeypatch.setattr(
        reviewer, "grade_answer",
        lambda q, f, l, d, a: reviewer.GradeResult(score=90 if "good" in a else 20, explanation="e", next_hint="h"),
    )
    monkeypatch.setattr(github, "approve_pr", lambda *args: None)
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def ticket(session: Session) -> Ticket:
    learner = progress.current_learner(session)
    project = Project(
        learner_id=learner.id, idea="A calculator", title="Calculator",  # type: ignore[arg-type]
        description="A command-line calculator for people learning to code.", repo_full_name="n3el-k/practice",
    )
    session.add(project)
    session.flush()
    row = Ticket(
        project_id=project.id, position=1, title="Evaluate a whole expression", why="Because.",  # type: ignore[arg-type]
        acceptance_criteria=["It works"], skill_areas=[SkillArea.backend, SkillArea.security],
    )
    session.add(row)
    session.commit()
    return row


def open_pr(session: Session, ticket: Ticket, number: int = 1) -> Gate:
    submission = Submission(
        learner_id=progress.current_learner(session).id, ticket_id=ticket.id,  # type: ignore[arg-type]
        repo_full_name="n3el-k/practice", pr_number=number,
        pr_url=f"https://github.com/n3el-k/practice/pull/{number}", head_sha="abc", diff="+ code",
    )
    session.add(submission)
    session.flush()
    gate = Gate(submission_id=submission.id)  # type: ignore[arg-type]
    session.add(gate)
    session.commit()
    return gate


def push(session: Session, gate: Gate, sha: str, injection: bool = False, questions: int = 2) -> list[Question]:
    """One reviewed push, as the webhook saves it."""
    submission = session.get(Submission, gate.submission_id)
    assert submission is not None
    review = Review(submission_id=submission.id, head_sha=sha, summary="s")  # type: ignore[arg-type]
    session.add(review)
    session.flush()
    if injection:
        session.add(
            Finding(
                review_id=review.id, kind=FindingKind.security, vuln_class="Code injection (CWE-94)",  # type: ignore[arg-type]
                file="calculator.py", line=32, explanation="eval runs any code a user types.",
                socratic_question="q", hints=["c", "w", "s"], hints_revealed=1,
            )
        )
    rows = [
        Question(gate_id=gate.id, review_id=review.id, text=f"Q{n} on {sha}")  # type: ignore[arg-type]
        for n in range(questions)
    ]
    session.add_all(rows)
    submission.head_sha = sha
    submission.status = SubmissionStatus.awaiting_gate
    gate.status = GateStatus.open
    session.add_all([submission, gate])
    session.commit()
    return rows


def answer(client: TestClient, gate: Gate, questions: list[Question], text: str) -> dict:
    response = client.post(
        f"/api/gates/{gate.id}/answers", json={"answers": [{"question_id": q.id, "text": text} for q in questions]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def skill(session: Session, area: SkillArea) -> int:
    session.expire_all()
    return session.exec(select(SkillScore).where(SkillScore.area == area)).one().score


# --- GET /api/portfolio --------------------------------------------------------


def test_a_new_learner_has_an_empty_portfolio(client: TestClient) -> None:
    body = client.get("/api/portfolio").json()
    assert body == {
        "learner": {"name": "Param Mehta", "github_login": "param-m1"},
        "projects": [],
        "security_fixes": [],
    }


def test_the_demo_loop_shows_up_in_the_portfolio(client: TestClient, session: Session, ticket: Ticket) -> None:
    # Push 1 has the eval() injection, push 2 fixes it, every answer passes.
    gate = open_pr(session, ticket)
    push(session, gate, "abc", injection=True)
    fixed = push(session, gate, "def")
    assert answer(client, gate, fixed, "a good answer")["passed"] is True

    body = client.get("/api/portfolio").json()
    [entry] = body["projects"]
    assert entry["title"] == "Calculator: Evaluate a whole expression"
    assert entry["pr_url"] == "https://github.com/n3el-k/practice/pull/1"
    assert entry["concepts"] == ["backend", "security"]
    assert entry["approved_at"]
    assert body["security_fixes"] == [{
        "vuln_class": "Code injection (CWE-94)", "file": "calculator.py",
        "pr_url": "https://github.com/n3el-k/practice/pull/1", "explanation": "eval runs any code a user types.",
    }]


def test_an_unapproved_pr_is_not_in_the_portfolio(client: TestClient, session: Session, ticket: Ticket) -> None:
    gate = open_pr(session, ticket)
    push(session, gate, "abc", injection=True)
    body = client.get("/api/portfolio").json()
    assert body["projects"] == [] and body["security_fixes"] == []


def test_newest_approval_first(client: TestClient, session: Session, ticket: Ticket) -> None:
    for number in (1, 2):
        gate = open_pr(session, ticket, number)
        answer(client, gate, push(session, gate, f"sha{number}"), "a good answer")
    urls = [e["pr_url"] for e in client.get("/api/portfolio").json()["projects"]]
    assert urls == ["https://github.com/n3el-k/practice/pull/2", "https://github.com/n3el-k/practice/pull/1"]


# --- The dashboard shows Claude's summary of the idea ----------------------------


def test_the_dashboard_project_has_its_summary(client: TestClient, ticket: Ticket) -> None:
    project = client.get("/api/dashboard").json()["current_project"]
    assert project["description"] == "A command-line calculator for people learning to code."


# --- gate_score: the latest push, and the weakest answer -------------------------


def test_old_pushes_answers_dont_count(client: TestClient, session: Session, ticket: Ticket) -> None:
    # Weak answers on push 1, then a new push answered well. Only push 2 should count,
    # so the pass earns its skill points. (Averaging both pushes gave 43 and no points.)
    gate = open_pr(session, ticket)
    old = push(session, gate, "abc")
    answer(client, gate, old, "dunno")
    new = push(session, gate, "def", questions=1)
    assert answer(client, gate, new, "a good answer")["passed"] is True
    assert progress.gate_score(session, gate.id) == 90  # type: ignore[arg-type]
    assert skill(session, SkillArea.backend) == 10


def test_the_score_is_the_weakest_answer(session: Session, ticket: Ticket) -> None:
    gate = open_pr(session, ticket)
    questions = push(session, gate, "abc")
    for q, score in zip(questions, (95, 60)):
        session.add(Answer(question_id=q.id, text="t", score=score, passed=score >= 70, explanation="e"))  # type: ignore[arg-type]
    session.commit()
    assert progress.gate_score(session, gate.id) == 60  # type: ignore[arg-type]
