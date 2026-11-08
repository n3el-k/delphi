"""Tests for POST /webhooks/github and the background review.

Payloads are signed with a test secret, the way GitHub signs them. GitHub and Claude are
replaced with fakes, so the tests run offline. TestClient runs background tasks right
after the response, so each test sees the finished review.
"""

import hashlib
import hmac
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401  (registers the tables)
from app.config import settings
from app.db import get_session
from app.main import app
from app.models import Finding, Gate, GateStatus, Project, Review, SkillArea, Submission, SubmissionStatus, Ticket
from app.seed import seed
from app.services import github, progress, reviewer

SECRET = "test-webhook-secret"
REPO = "n3el-k/practice"
DIFF = "diff --git a/calculator.py b/calculator.py\n+    return eval(expression)\n"

REVIEW = reviewer.ReviewResult(
    summary="Clear structure. One input needs a closer look.",
    findings=[
        reviewer.ReviewFinding(
            kind="security",
            vuln_class="Code injection (CWE-94)",
            file="calculator.py",
            line=32,
            explanation="eval runs any Python the user types.",
            socratic_question="What would happen if someone typed __import__('os') here?",
            hints=reviewer.HintLadder(
                concept="Never run user input as code.",
                where_to_look="Look at line 32.",
                snippet="int('42')",
            ),
        )
    ],
    policy_flags=[],
)


# --- Fixtures ------------------------------------------------------------------


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed(s)
        yield s


@pytest.fixture
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "github_webhook_secret", SecretStr(SECRET))
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Fake GitHub and Claude. Records what the bot would have posted."""
    calls: dict = {"comments": [], "reviews": 0}

    def review_diff(diff: str, ticket: reviewer.TicketContext) -> reviewer.ReviewResult:
        calls["reviews"] += 1
        calls["ticket"] = ticket.title
        return REVIEW

    def post_comment(repo: str, number: int, body: str) -> int:
        calls["comments"].append(body)
        return 999

    monkeypatch.setattr(github, "get_pr_diff", lambda repo, number: DIFF)
    monkeypatch.setattr(github, "post_comment", post_comment)
    monkeypatch.setattr(reviewer, "review_diff", review_diff)
    return calls


@pytest.fixture
def tickets(session: Session) -> list[Ticket]:
    learner = progress.current_learner(session)
    project = Project(
        learner_id=learner.id, idea="A calculator", title="Calculator",  # type: ignore[arg-type]
        description="A calculator.", repo_full_name=REPO,
    )
    session.add(project)
    session.flush()
    rows = [
        Ticket(
            project_id=project.id, position=i, title=f"Ticket {i}", why="Because.",  # type: ignore[arg-type]
            acceptance_criteria=["It works"], skill_areas=[SkillArea.backend],
        )
        for i in range(1, 4)
    ]
    session.add_all(rows)
    session.commit()
    return rows


# --- Helpers -------------------------------------------------------------------


def pr_event(action: str = "opened", body: str | None = None, sha: str = "abc123", repo: str = REPO) -> dict:
    return {
        "action": action,
        "pull_request": {
            "number": 1,
            "html_url": f"https://github.com/{repo}/pull/1",
            "body": body,
            "head": {"sha": sha},
            "user": {"login": "param-m1"},
        },
        "repository": {"full_name": repo},
    }


def deliver(client: TestClient, payload: dict, event: str = "pull_request", secret: str = SECRET):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/github",
        content=body,
        headers={"X-GitHub-Event": event, "X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )


# --- Signatures ----------------------------------------------------------------


def test_rejects_a_wrong_signature(client: TestClient, fakes: dict) -> None:
    assert deliver(client, pr_event(), secret="not-the-secret").status_code == 401
    assert fakes["reviews"] == 0


def test_rejects_a_missing_signature(client: TestClient) -> None:
    response = client.post("/webhooks/github", json=pr_event(), headers={"X-GitHub-Event": "pull_request"})
    assert response.status_code == 401


def test_rejects_everything_when_no_secret_is_set(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "github_webhook_secret", None)
    assert deliver(client, pr_event()).status_code == 401


def test_rejects_a_tampered_body(client: TestClient) -> None:
    body = json.dumps(pr_event()).encode()
    signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/github",
        content=body.replace(b"opened", b"closed"),
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": signature},
    )
    assert response.status_code == 401


# --- What gets ignored ---------------------------------------------------------


def test_ping(client: TestClient) -> None:
    response = deliver(client, {"zen": "Keep it logically awesome."}, event="ping")
    assert response.status_code == 200
    assert response.json() == {"status": "pong"}


def test_ignores_other_events_and_actions(client: TestClient, tickets: list[Ticket], fakes: dict) -> None:
    assert deliver(client, {"ref": "main"}, event="push").json() == {"status": "ignored"}
    assert deliver(client, pr_event(action="closed")).json() == {"status": "ignored"}
    assert fakes["reviews"] == 0


def test_ignores_a_repo_no_project_links(client: TestClient, tickets: list[Ticket], fakes: dict) -> None:
    response = deliver(client, pr_event(repo="someone/else"))
    assert response.status_code == 202
    assert response.json() == {"status": "ignored"}
    assert fakes["reviews"] == 0


def test_rejects_a_malformed_pull_request_payload(client: TestClient) -> None:
    assert deliver(client, {"action": "opened"}).status_code == 422


# --- The loop ------------------------------------------------------------------


def test_opened_pr_is_reviewed_and_the_gate_opens(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    response = deliver(client, pr_event())
    assert response.status_code == 202
    assert response.json() == {"status": "reviewing"}

    submission = session.exec(select(Submission)).one()
    assert submission.diff == DIFF
    assert submission.status == SubmissionStatus.awaiting_gate
    assert submission.ticket_id == tickets[0].id

    gate = session.exec(select(Gate)).one()
    assert gate.status == GateStatus.open

    review = session.exec(select(Review)).one()
    assert review.head_sha == "abc123"
    assert review.github_comment_id == 999

    finding = session.exec(select(Finding)).one()
    assert finding.hints == ["Never run user input as code.", "Look at line 32.", "int('42')"]
    assert finding.hints_revealed == 1

    [comment] = fakes["comments"]
    assert "Code injection (CWE-94)" in comment
    assert "Never run user input as code." in comment
    assert "int('42')" not in comment  # the later rungs only unlock in the app
    assert f"/gates/{gate.id}" in comment


def test_ticket_named_in_the_description(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    deliver(client, pr_event(body=f"Adds the parser.\n\nTicket: #{tickets[2].id}"))
    assert session.exec(select(Submission)).one().ticket_id == tickets[2].id
    assert fakes["ticket"] == "Ticket 3"


def test_unknown_ticket_number_falls_back_to_the_first_ticket(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    deliver(client, pr_event(body="Ticket: #9999"))
    assert session.exec(select(Submission)).one().ticket_id == tickets[0].id


def test_a_new_push_reuses_the_submission_and_adds_a_review(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    deliver(client, pr_event())
    deliver(client, pr_event(action="synchronize", sha="def456"))

    submission = session.exec(select(Submission)).one()
    assert submission.head_sha == "def456"
    assert len(session.exec(select(Gate)).all()) == 1
    assert [r.head_sha for r in session.exec(select(Review)).all()] == ["abc123", "def456"]
    assert len(fakes["comments"]) == 2


def test_an_approved_pr_is_not_reopened(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    deliver(client, pr_event())
    submission = session.exec(select(Submission)).one()
    submission.status = SubmissionStatus.approved
    session.add(submission)
    session.commit()

    assert deliver(client, pr_event(action="synchronize", sha="def456")).json() == {"status": "ignored"}
    assert fakes["reviews"] == 1


def test_a_failed_review_leaves_the_gate_reviewing(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(diff: str, ticket: reviewer.TicketContext) -> reviewer.ReviewResult:
        raise reviewer.ReviewerError("Claude timed out")

    monkeypatch.setattr(reviewer, "review_diff", fail)
    assert deliver(client, pr_event()).status_code == 202
    assert session.exec(select(Gate)).one().status == GateStatus.reviewing
    assert session.exec(select(Review)).all() == []
    assert fakes["comments"] == []


def test_a_failed_comment_still_opens_the_gate(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(repo: str, number: int, body: str) -> int:
        raise github.GitHubError("GitHub POST returned 502")

    monkeypatch.setattr(github, "post_comment", fail)
    deliver(client, pr_event())
    assert session.exec(select(Gate)).one().status == GateStatus.open
    assert session.exec(select(Review)).one().github_comment_id is None


# --- Repeat deliveries ---------------------------------------------------------


def test_a_repeat_delivery_of_the_same_push_is_ignored(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    # Seen live: a second smee client forwarded every event twice.
    deliver(client, pr_event())
    assert deliver(client, pr_event()).json() == {"status": "ignored"}
    assert fakes["reviews"] == 1
    assert len(fakes["comments"]) == 1
    assert len(session.exec(select(Review)).all()) == 1


def test_reopening_retries_a_push_whose_review_failed(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(diff: str, ticket: reviewer.TicketContext) -> reviewer.ReviewResult:
        raise reviewer.ReviewerError("Claude timed out")

    monkeypatch.setattr(reviewer, "review_diff", fail)
    deliver(client, pr_event())
    monkeypatch.setattr(reviewer, "review_diff", lambda diff, ticket: REVIEW)

    assert deliver(client, pr_event(action="reopened")).json() == {"status": "reviewing"}
    assert session.exec(select(Gate)).one().status == GateStatus.open
    assert len(session.exec(select(Review)).all()) == 1


def test_reopening_an_already_reviewed_push_keeps_the_gate_open(
    client: TestClient, session: Session, tickets: list[Ticket], fakes: dict
) -> None:
    deliver(client, pr_event())
    assert deliver(client, pr_event(action="reopened")).json() == {"status": "ignored"}
    assert session.exec(select(Gate)).one().status == GateStatus.open
    assert fakes["reviews"] == 1
