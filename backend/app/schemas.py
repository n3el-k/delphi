"""Request and response models: the API contract v1 (plans/project-plan.md).

The frontend generates its TypeScript types from these through /openapi.json,
so this file is the single source of truth. Neel's gate and flag models go here too.
"""

from pydantic import BaseModel

from app.models import FindingKind, GateStatus, SkillArea
from app.services.progress import TicketStatus

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


class TicketOut(BaseModel):
    id: int
    title: str
    why: str
    acceptance_criteria: list[str]
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
