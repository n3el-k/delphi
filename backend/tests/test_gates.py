"""Tests for the comprehension gate endpoints.

Each test builds the state the webhook would leave behind (a submission, its gate, and
one review per push with findings and questions) straight in a fresh in-memory DB.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

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
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.seed import seed
from app.services import progress

HINTS = ["Never run user input as code.", "Look at line 32.", "int('42')"]


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


@pytest.fixture
def gate(session: Session) -> Gate:
    """A PR whose gate is still waiting for its first review."""
    learner = progress.current_learner(session)
    project = Project(
        learner_id=learner.id, idea="A calculator", title="Calculator",  # type: ignore[arg-type]
        description="A calculator.", repo_full_name="n3el-k/practice",
    )
    session.add(project)
    session.flush()
    ticket = Ticket(
        project_id=project.id, position=1, title="Evaluate a whole expression", why="Because.",  # type: ignore[arg-type]
        acceptance_criteria=["It works"], skill_areas=[SkillArea.backend, SkillArea.security],
    )
    session.add(ticket)
    session.flush()
    submission = Submission(
        learner_id=learner.id, ticket_id=ticket.id, repo_full_name="n3el-k/practice", pr_number=1,  # type: ignore[arg-type]
        pr_url="https://github.com/n3el-k/practice/pull/1", head_sha="abc123", diff="+ eval(x)",
    )
    session.add(submission)
    session.flush()
    gate = Gate(submission_id=submission.id)  # type: ignore[arg-type]
    session.add(gate)
    session.commit()
    return gate


def add_push(
    session: Session, gate: Gate, sha: str, security: bool = True, questions: int = 2, hints_revealed: int = 1
) -> tuple[Review, list[Finding], list[Question]]:
    """What the webhook saves for one reviewed push."""
    submission = session.get(Submission, gate.submission_id)
    assert submission is not None
    review = Review(submission_id=submission.id, head_sha=sha, summary=f"Review of {sha}.")  # type: ignore[arg-type]
    session.add(review)
    session.flush()
    findings = []
    if security:
        findings.append(
            Finding(
                review_id=review.id, kind=FindingKind.security, vuln_class="Code injection (CWE-94)",  # type: ignore[arg-type]
                file="calculator.py", line=32, explanation="eval runs any code.",
                socratic_question="What else would eval run?", hints=HINTS, hints_revealed=hints_revealed,
            )
        )
    session.add_all(findings)
    session.flush()
    rows = [
        Question(
            gate_id=gate.id, review_id=review.id, text=f"Question {n} on {sha}", file="calculator.py", line=30 + n,  # type: ignore[arg-type]
            finding_id=findings[0].id if findings and n == 1 else None,
        )
        for n in range(1, questions + 1)
    ]
    session.add_all(rows)
    submission.head_sha = sha
    submission.status = SubmissionStatus.awaiting_gate
    gate.status = GateStatus.open
    session.add_all([submission, gate])
    session.commit()
    return review, findings, rows


# --- GET /api/gates/{id} -------------------------------------------------------


def test_unknown_gate_is_404(client: TestClient) -> None:
    assert client.get("/api/gates/999").status_code == 404


def test_a_gate_still_reviewing_has_no_review_yet(client: TestClient, gate: Gate) -> None:
    body = client.get(f"/api/gates/{gate.id}").json()
    assert body["status"] == "reviewing"
    assert body["review"] is None
    assert body["findings"] == [] and body["questions"] == []
    assert body["ticket_title"] == "Evaluate a whole expression"
    assert body["pr_url"] == "https://github.com/n3el-k/practice/pull/1"


def test_an_open_gate_shows_its_review(client: TestClient, session: Session, gate: Gate) -> None:
    review, _, questions = add_push(session, gate, "abc123")
    body = client.get(f"/api/gates/{gate.id}").json()
    assert body["status"] == "open"
    assert body["review"] == {"id": review.id, "summary": "Review of abc123.", "is_fallback": False}
    [finding] = body["findings"]
    assert finding["vuln_class"] == "Code injection (CWE-94)"
    assert [q["id"] for q in body["questions"]] == [q.id for q in questions]
    assert body["questions"][0]["last_answer"] is None


def test_only_revealed_hints_are_sent(client: TestClient, session: Session, gate: Gate) -> None:
    # Sending all three and hiding them in the UI would let a learner read the snippet in devtools.
    add_push(session, gate, "abc123", hints_revealed=1)
    assert client.get(f"/api/gates/{gate.id}").json()["findings"][0]["hints"] == HINTS[:1]


def test_shows_only_the_latest_push(client: TestClient, session: Session, gate: Gate) -> None:
    add_push(session, gate, "abc123")
    review, _, questions = add_push(session, gate, "def456", security=False, questions=3)
    body = client.get(f"/api/gates/{gate.id}").json()
    assert body["review"]["id"] == review.id
    assert body["findings"] == []
    assert [q["text"] for q in body["questions"]] == [q.text for q in questions]


def test_shows_the_latest_answer(client: TestClient, session: Session, gate: Gate) -> None:
    _, _, questions = add_push(session, gate, "abc123")
    for score in (40, 85):
        session.add(
            Answer(
                question_id=questions[0].id, text=f"Attempt scoring {score}", score=score,  # type: ignore[arg-type]
                passed=score >= 70, explanation="Because.", next_hint=None,
            )
        )
    session.commit()
    answer = client.get(f"/api/gates/{gate.id}").json()["questions"][0]["last_answer"]
    assert answer["score"] == 85 and answer["passed"] is True
    assert answer["text"] == "Attempt scoring 85"
