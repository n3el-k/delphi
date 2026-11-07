"""Request and response models: the API contract v1 (plans/project-plan.md).

The frontend generates its TypeScript types from these through /openapi.json,
so this file is the single source of truth. Neel's gate and flag models go here too.
"""

from typing import Literal

from pydantic import BaseModel

from app.models import SkillArea, TicketSize

# --- GET /api/me ---


class LevelRef(BaseModel):
    number: int
    name: str


class MeOut(BaseModel):
    name: str
    github_login: str
    current_level: LevelRef


# --- GET /api/levels ---


class LevelRequirements(BaseModel):
    projects: int
    min_gate_score: int
    security_fixes: int


class LevelOut(BaseModel):
    number: int
    name: str
    ai_policy: str
    starts_at: TicketSize
    ends_at: TicketSize
    review_focus: str
    unlocks: list[str]
    requirements: LevelRequirements
    status: Literal["done", "current", "locked"]


# --- GET /api/dashboard ---


class SkillOut(BaseModel):
    area: SkillArea
    score: int


class ProjectRef(BaseModel):
    id: int
    title: str


class TicketOut(BaseModel):
    id: int
    size: TicketSize
    title: str
    why: str
    acceptance_criteria: list[str]


class Count(BaseModel):
    done: int
    required: int


class ProgressOut(BaseModel):
    projects: Count
    security_fixes: Count


class DashboardOut(BaseModel):
    skills: list[SkillOut]
    # null only once every project on the current level is done
    current_project: ProjectRef | None
    current_ticket: TicketOut | None
    open_gate_id: int | None
    progress: ProgressOut
