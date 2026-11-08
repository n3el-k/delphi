"""Tests for the comprehension gate endpoints.

Each test builds the state the webhook would leave behind (a submission, its gate, and
one review per push with findings and questions) straight in a fresh in-memory DB.
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
    """What the webhook saves for one reviewed push, including dropping the last push's
    unanswered questions."""
    submission = session.get(Submission, gate.submission_id)
    assert submission is not None
    for old in session.exec(select(Question).where(Question.gate_id == gate.id)).all():
        if session.exec(select(Answer).where(Answer.question_id == old.id)).first() is None:
            session.delete(old)
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


# --- POST /api/gates/{id}/answers ----------------------------------------------


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Fake grader and GitHub. An answer containing "good" scores 90, anything else 40."""
    calls: dict = {"approved": [], "graded": []}

    def grade_answer(question, file, line, diff, answer) -> reviewer.GradeResult:
        calls["graded"].append(answer)
        good = "good" in answer
        return reviewer.GradeResult(
            score=90 if good else 40,
            explanation="Clear and specific." if good else "Too vague.",
            next_hint="" if good else "Think about what the user can type.",
        )

    monkeypatch.setattr(reviewer, "grade_answer", grade_answer)
    monkeypatch.setattr(github, "approve_pr", lambda repo, number, sha, body: calls["approved"].append((repo, number, sha)))
    return calls


def answer(client: TestClient, gate: Gate, *pairs: tuple[Question, str]):
    return client.post(
        f"/api/gates/{gate.id}/answers",
        json={"answers": [{"question_id": q.id, "text": text} for q, text in pairs]},
    )


def test_answers_on_a_reviewing_gate_are_refused(client: TestClient, gate: Gate, fakes: dict) -> None:
    response = client.post(f"/api/gates/{gate.id}/answers", json={"answers": [{"question_id": 1, "text": "x"}]})
    assert response.status_code == 409


def test_answers_wait_until_the_security_finding_is_fixed(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    _, _, questions = add_push(session, gate, "abc123", security=True)
    response = answer(client, gate, (questions[0], "a good answer"))
    assert response.status_code == 409
    assert "security" in response.json()["detail"]
    assert fakes["graded"] == []


def test_a_question_from_another_push_is_rejected(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    _, _, old = add_push(session, gate, "abc123", security=False)
    add_push(session, gate, "def456", security=False)
    assert answer(client, gate, (old[0], "a good answer")).status_code == 422


def test_answer_text_is_validated(client: TestClient, session: Session, gate: Gate, fakes: dict) -> None:
    _, _, questions = add_push(session, gate, "abc123", security=False)
    assert answer(client, gate, (questions[0], "")).status_code == 422
    assert answer(client, gate, (questions[0], "x" * 2001)).status_code == 422
    assert client.post(f"/api/gates/{gate.id}/answers", json={"answers": []}).status_code == 422


def test_a_weak_answer_fails_with_a_hint_and_nothing_is_approved(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    _, _, questions = add_push(session, gate, "def456", security=False)
    body = answer(client, gate, (questions[0], "a good answer"), (questions[1], "dunno")).json()
    assert body["passed"] is False
    weak = body["results"][1]
    assert weak == {
        "question_id": questions[1].id, "score": 40, "passed": False,
        "explanation": "Too vague.", "next_hint": "Think about what the user can type.",
    }
    assert body["results"][0]["next_hint"] is None
    assert fakes["approved"] == []
    assert session.get(Gate, gate.id).status == GateStatus.open  # type: ignore[union-attr]


def test_only_the_failed_question_needs_answering_again(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    _, _, questions = add_push(session, gate, "def456", security=False)
    answer(client, gate, (questions[0], "a good answer"), (questions[1], "dunno"))
    body = answer(client, gate, (questions[1], "now a good answer")).json()
    assert body["passed"] is True
    assert len(session.exec(select(Answer)).all()) == 3  # every attempt is kept


def test_a_failed_answer_on_a_finding_climbs_its_hint_ladder(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    # A correctness finding (security ones block answering) linked to the first question.
    review, _, questions = add_push(session, gate, "def456", security=False)
    finding = Finding(
        review_id=review.id, kind=FindingKind.correctness, file="calculator.py", line=33,  # type: ignore[arg-type]
        explanation="1 / 0 crashes.", socratic_question="What does 1 / 0 raise?", hints=HINTS, hints_revealed=1,
    )
    session.add(finding)
    session.flush()
    questions[0].finding_id = finding.id
    session.add(questions[0])
    session.commit()

    hints = [answer(client, gate, (questions[0], "dunno")).json()["results"][0]["next_hint"] for _ in range(3)]
    # Rungs 2 and 3 of the ladder, then the grader's own hint once the ladder runs out.
    assert hints == [HINTS[1], HINTS[2], "Think about what the user can type."]
    assert client.get(f"/api/gates/{gate.id}").json()["findings"][0]["hints"] == HINTS


def test_passing_approves_the_pr_and_updates_the_skill_map(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    # The demo: push 1 has the eval() finding, push 2 fixes it and every answer passes.
    _, [injection], _ = add_push(session, gate, "abc123", security=True)
    _, _, questions = add_push(session, gate, "def456", security=False)

    body = answer(client, gate, *[(q, "a good answer") for q in questions]).json()
    assert body["passed"] is True
    assert fakes["approved"] == [("n3el-k/practice", 1, "def456")]

    session.expire_all()
    gate_row = session.get(Gate, gate.id)
    assert gate_row.status == GateStatus.passed and gate_row.passed_at is not None  # type: ignore[union-attr]
    assert session.get(Submission, gate.submission_id).status == SubmissionStatus.approved  # type: ignore[union-attr]
    assert session.get(Finding, injection.id).resolved is True  # type: ignore[union-attr]

    learner = progress.current_learner(session)
    scores = {s.area: s.score for s in session.exec(select(SkillScore).where(SkillScore.learner_id == learner.id))}
    # 10 per ticket area, plus 5 security for the fixed injection.
    assert scores[SkillArea.backend] == 10
    assert scores[SkillArea.security] == 15

    assert answer(client, gate, (questions[0], "a good answer")).status_code == 409  # already passed


def test_a_problem_reported_on_two_pushes_counts_as_one_fix(
    client: TestClient, session: Session, gate: Gate, fakes: dict
) -> None:
    _, [first], _ = add_push(session, gate, "abc123", security=True)
    _, [second], _ = add_push(session, gate, "bcd234", security=True)
    _, _, questions = add_push(session, gate, "def456", security=False)
    answer(client, gate, *[(q, "a good answer") for q in questions])
    session.expire_all()
    assert session.get(Finding, first.id).resolved is False  # type: ignore[union-attr]
    assert session.get(Finding, second.id).resolved is True  # type: ignore[union-attr]


def test_the_pass_stands_if_github_cannot_approve(
    client: TestClient, session: Session, gate: Gate, fakes: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args):
        raise github.GitHubError("GitHub POST returned 502")

    monkeypatch.setattr(github, "approve_pr", fail)
    _, _, questions = add_push(session, gate, "def456", security=False)
    assert answer(client, gate, *[(q, "a good answer") for q in questions]).json()["passed"] is True
    session.expire_all()
    assert session.get(Gate, gate.id).status == GateStatus.passed  # type: ignore[union-attr]


def test_a_grading_failure_saves_nothing(
    client: TestClient, session: Session, gate: Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*args):
        raise reviewer.ReviewerError("Claude timed out")

    monkeypatch.setattr(reviewer, "grade_answer", fail)
    _, _, questions = add_push(session, gate, "def456", security=False)
    assert answer(client, gate, (questions[0], "a good answer")).status_code == 503
    assert session.exec(select(Answer)).all() == []
