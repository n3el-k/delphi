"""Seed data: one learner and their starting skill map. No projects.

Run with `uv run python -m app.seed`. It wipes the database and starts fresh.
The learner starts brand new: no fake history and no pre-made projects.
Their first project comes from an idea they type in (POST /api/projects),
and all progress comes from real PRs.
"""

from sqlmodel import Session, SQLModel

from app.config import settings
from app.db import create_db, engine
from app.models import Learner, SkillArea, SkillScore

STARTING_SKILLS = {area: 0 for area in SkillArea}


def seed(session: Session) -> None:
    # 1. The learner first: their skill scores need their ID.
    learner = Learner(name="Param Mehta", github_login=settings.demo_learner_github_login)
    session.add(learner)
    session.flush()  # sends the insert so the database assigns learner.id
    assert learner.id is not None

    # 2. Their starting skill map: every area at 0.
    session.add_all(
        SkillScore(learner_id=learner.id, area=area, score=score)
        for area, score in STARTING_SKILLS.items()
    )

    # 3. Save everything at once. If anything above failed, nothing is saved.
    session.commit()


def reset_and_seed() -> None:
    SQLModel.metadata.drop_all(engine)
    create_db()
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    reset_and_seed()
    print("Seeded: 1 learner with a starting skill map, no projects.")
