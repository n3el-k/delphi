"""Request and response models: the API contract v1 (plans/project-plan.md).

The frontend generates its TypeScript types from these through /openapi.json,
so this file is the single source of truth. Neel's gate and flag models go here too.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models import FindingKind, GateStatus, SkillArea, TicketStatus

# Any id a client sends us. SQLite and Postgres ids are 64-bit, so a bigger number would
# overflow inside the database and come back as a 500. This turns it into a 422 up front.
MAX_DB_ID = 2**63 - 1
DbId = Annotated[int, Field(ge=1, le=MAX_DB_ID)]

# --- GET /api/me ---


class MeOut(BaseModel):
    name: str
    github_login: str


# --- GET /api/dashboard ---


class SkillOut(BaseModel):
    area: SkillArea
    score: int


class ProjectRef(BaseModel):
    id: int
    title: str
    description: str  # Claude's summary of the idea, so the learner sees how it was understood


class TicketBase(BaseModel):
    """The ticket fields every response shares."""

    id: int
    title: str
    why: str
    acceptance_criteria: list[str]


class TicketOut(TicketBase):
    """A ticket on the dashboard: the shared fields plus where the learner is with it."""

    status: TicketStatus


class DashboardOut(BaseModel):
    skills: list[SkillOut]
    # null once every project is done
    current_project: ProjectRef | None
    # the current project's tickets, in order (empty when there's no current project)
    tickets: list[TicketOut]
    open_gate_id: int | None


# --- GET /api/gates/{id} (Neel) ---


class GateReviewOut(BaseModel):
    id: int
    summary: str
    is_fallback: bool


class FindingOut(BaseModel):
    id: int
    kind: FindingKind
    vuln_class: str | None
    file: str
    line: int | None
    explanation: str
    socratic_question: str
    # Only the hints already revealed, in ladder order. The rest never leave the server.
    hints: list[str]
    resolved: bool


class AnswerOut(BaseModel):
    # The id to send as answer_id when flagging this grade.
    id: int
    text: str
    score: int
    passed: bool
    explanation: str
    next_hint: str | None


class QuestionOut(BaseModel):
    id: int
    text: str
    file: str | None
    line: int | None
    last_answer: AnswerOut | None


class GateOut(BaseModel):
    id: int
    status: GateStatus
    pr_url: str
    ticket_title: str
    # The latest push's review, findings and questions. review is null while the first one runs.
    review: GateReviewOut | None
    findings: list[FindingOut]
    questions: list[QuestionOut]


# --- POST /api/gates/{id}/answers (Neel) ---


class AnswerIn(BaseModel):
    question_id: DbId
    text: str = Field(min_length=1, max_length=2000)


class AnswersIn(BaseModel):
    # Only the questions not passed yet need answering again. A push has at most 3 questions.
    answers: list[AnswerIn] = Field(min_length=1, max_length=3)


class AnswerResult(BaseModel):
    question_id: int
    # The saved attempt, so a grade can be flagged straight away without refetching the gate.
    answer_id: int
    score: int
    passed: bool
    explanation: str
    next_hint: str | None


class AnswersOut(BaseModel):
    # true when every question on the latest push has passed: the PR is approved
    passed: bool
    results: list[AnswerResult]


# --- POST /api/reviews/{id}/flag (Neel) ---


class FlagIn(BaseModel):
    # Trimmed first, so a reason of only spaces counts as empty.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    # Leave both out to flag the whole review. Each must belong to the flagged review's PR.
    finding_id: DbId | None = None
    answer_id: DbId | None = None


class FlagOut(BaseModel):
    id: int
    created_at: datetime


# --- GET /api/portfolio ---


class PortfolioLearner(BaseModel):
    name: str
    github_login: str


class PortfolioEntry(BaseModel):
    # One per approved PR: "<project>: <ticket>"
    title: str
    pr_url: str
    approved_at: datetime
    # The skill areas the ticket exercised
    concepts: list[str]


class SecurityFixOut(BaseModel):
    vuln_class: str
    file: str
    pr_url: str
    # What was wrong, in the AI reviewer's words
    explanation: str


class PortfolioOut(BaseModel):
    learner: PortfolioLearner
    # newest first
    projects: list[PortfolioEntry]
    security_fixes: list[SecurityFixOut]


# --- POST /api/projects ---


class ProjectIn(BaseModel):
    # Trim spaces from every string before validating, so "   " counts as empty.
    model_config = ConfigDict(str_strip_whitespace=True)

    idea: str = Field(min_length=1, max_length=1000)
    # GitHub "owner/name": owner is letters, digits and hyphens (max 39, no leading hyphen);
    # name is letters, digits, ".", "_" and "-" (max 100).
    repo_full_name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}$")

    @field_validator("repo_full_name")
    @classmethod
    def repo_name_is_not_only_dots(cls, value: str) -> str:
        # The pattern allows dots, so "owner/." and "owner/.." would match. GitHub doesn't allow
        # those names, and ".." in an API URL could point at a different endpoint (path traversal).
        name = value.split("/")[1]
        if set(name) == {"."}:
            raise ValueError("repo name can't be only dots")
        return value


class ProjectOut(BaseModel):
    """The project just created, with the tickets generated from the idea."""

    id: int
    title: str
    # Claude's one-paragraph summary of how it understood the idea (at most 500 characters)
    description: str
    # True when Claude was unavailable and these are the cached example tickets
    is_fallback: bool
    tickets: list[TicketBase]
