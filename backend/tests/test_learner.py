from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.db import get_session
from app.main import app
from app.models import Finding, FindingKind, Gate, GateStatus, Review, Submission, SubmissionStatus
from app.seed import seed


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


def test_me(client: TestClient) -> None:
    body = client.get("/api/me").json()
    assert body["github_login"] == "param-m1"
    assert body["current_level"] == {"number": 1, "name": "Foundations"}


def test_levels_status(client: TestClient) -> None:
    levels = client.get("/api/levels").json()
    assert [lv["status"] for lv in levels] == ["current", "locked", "locked", "locked"]
    assert levels[0]["requirements"] == {"projects": 2, "min_gate_score": 70, "security_fixes": 1}
    assert all(lv["unlocks"] and lv["ai_policy"] for lv in levels)


def test_dashboard_fresh_learner(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert len(body["skills"]) == 7
    assert body["current_project"]["title"] == "Calculator"
    assert body["current_ticket"]["title"] == "Evaluate arithmetic expressions"
    assert body["open_gate_id"] is None
    assert body["progress"] == {
        "projects": {"done": 0, "required": 2},
        "security_fixes": {"done": 0, "required": 1},
    }


def _submit_calculator(session: Session, status: SubmissionStatus) -> Submission:
    sub = Submission(
        learner_id=1, ticket_id=1, repo_full_name="n3el-k/level1-calculator", pr_number=1,
        pr_url="https://github.com/n3el-k/level1-calculator/pull/1", head_sha="abc", diff="", status=status,
    )
    session.add(sub)
    session.flush()
    return sub


def test_dashboard_open_gate(client: TestClient, session: Session) -> None:
    sub = _submit_calculator(session, SubmissionStatus.awaiting_gate)
    gate = Gate(submission_id=sub.id, status=GateStatus.open)  # type: ignore[arg-type]
    session.add(gate)
    session.commit()
    assert client.get("/api/dashboard").json()["open_gate_id"] == gate.id


def test_dashboard_after_approved_security_fix(client: TestClient, session: Session) -> None:
    sub = _submit_calculator(session, SubmissionStatus.approved)
    review = Review(submission_id=sub.id, head_sha="abc", summary="s")  # type: ignore[arg-type]
    session.add(review)
    session.flush()
    session.add(
        Finding(
            review_id=review.id, kind=FindingKind.security, vuln_class="code injection",  # type: ignore[arg-type]
            file="calc.py", line=3, explanation="e", socratic_question="q", resolved=True,
        )
    )
    session.add(Gate(submission_id=sub.id, status=GateStatus.passed))  # type: ignore[arg-type]
    session.commit()

    body = client.get("/api/dashboard").json()
    assert body["progress"]["projects"]["done"] == 1
    assert body["progress"]["security_fixes"]["done"] == 1
    assert body["current_project"]["title"] == "To-do app"
    assert body["open_gate_id"] is None
