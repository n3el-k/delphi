"""Database tables, exactly as agreed in data model v1 (plans/project-plan.md)."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class SkillArea(StrEnum):
    frontend = "frontend"
    backend = "backend"
    database = "database"
    git = "git"
    debugging = "debugging"
    security = "security"
    testing = "testing"


class TicketLabel(StrEnum):
    core = "core"
    delegable = "delegable"


class SubmissionStatus(StrEnum):
    reviewing = "reviewing"
    awaiting_gate = "awaiting_gate"
    approved = "approved"


class GateStatus(StrEnum):
    reviewing = "reviewing"
    open = "open"
    passed = "passed"


class FindingKind(StrEnum):
    security = "security"
    correctness = "correctness"


# --- Projects and tickets (from the learner's idea, or the seeded demo) ---


class Project(SQLModel, table=True):
    # One learner can't have two projects with the same idea and repo. The database enforces it,
    # so even two requests at the same moment (a double-click) can't both save one.
    __table_args__ = (UniqueConstraint("learner_id", "idea", "repo_full_name"),)

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")  # whose project this is
    idea: str  # what the learner typed; Claude turns it into tickets
    title: str
    description: str  # Claude's summary of the idea, shown on the dashboard (at most 500 characters)
    repo_full_name: str  # the learner's GitHub repo, "owner/name"
    is_fallback: bool = False  # True when these are the cached example tickets, not Claude's


class Ticket(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id")
    position: int  # order of the ticket within its project
    title: str
    why: str
    acceptance_criteria: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skill_areas: list[SkillArea] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    label: TicketLabel | None = None


# --- Learner ---


class Learner(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    github_login: str = Field(unique=True)


class SkillScore(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("learner_id", "area"),)

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    area: SkillArea
    score: int = Field(ge=0, le=100)


# --- GitHub loop ---


class Submission(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("repo_full_name", "pr_number"),)

    id: int | None = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="learner.id")
    ticket_id: int = Field(foreign_key="ticket.id")
    repo_full_name: str
    pr_number: int
    pr_url: str
    head_sha: str
    diff: str
    status: SubmissionStatus = SubmissionStatus.reviewing
    created_at: datetime = Field(default_factory=_now)


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id")
    head_sha: str
    summary: str
    policy_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    github_comment_id: int | None = None
    is_fallback: bool = False
    created_at: datetime = Field(default_factory=_now)


class Finding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="review.id")
    kind: FindingKind
    vuln_class: str | None = None
    file: str
    line: int | None = None
    explanation: str
    socratic_question: str
    # The hint ladder: [concept, where_to_look, snippet]
    hints: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    hints_revealed: int = 0
    resolved: bool = False


class Gate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    submission_id: int = Field(foreign_key="submission.id", unique=True)
    status: GateStatus = GateStatus.reviewing
    passed_at: datetime | None = None


class Question(SQLModel, table=True):
    # The webhook deletes a push's unanswered questions when a new push lands. Without this,
    # SQLite hands their ids to the new questions, and a stale browser tab's answer to an
    # old question would be graded against a new one.
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    gate_id: int = Field(foreign_key="gate.id")
    # The push (review) this question was asked about. The gate shows the latest push's
    # questions, and older ones stay for the "why this grade" history.
    review_id: int | None = Field(default=None, foreign_key="review.id")
    finding_id: int | None = Field(default=None, foreign_key="finding.id")
    text: str
    file: str | None = None
    line: int | None = None


class Answer(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    text: str
    score: int
    passed: bool
    explanation: str
    next_hint: str | None = None
    created_at: datetime = Field(default_factory=_now)


class Flag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="review.id")
    finding_id: int | None = Field(default=None, foreign_key="finding.id")
    answer_id: int | None = Field(default=None, foreign_key="answer.id")
    reason: str
    created_at: datetime = Field(default_factory=_now)
