"""Seed data: one learner and the demo projects (the calculator with the eval() trap, and a to-do list).

Run with `uv run python -m app.seed`. It wipes the database and starts fresh.
The learner starts brand new: no fake history. All progress comes from real PRs.
"""

from sqlmodel import Session, SQLModel

from app.config import settings
from app.db import create_db, engine
from app.models import Learner, Project, SkillArea, SkillScore, Ticket

# Practice repos the learner opens PRs on (Python). Neel's GitHub App watches these.
# Update once Neel has created them.
CALCULATOR_REPO = "n3el-k/level1-calculator"
TODO_REPO = "n3el-k/level1-todo"


def demo_project(learner_id: int) -> list[tuple[Project, list[Ticket]]]:
    """The demo projects for a learner. The calculator's last ticket is the eval() trap."""
    calculator = Project(
        learner_id=learner_id,
        idea="A calculator I can type maths expressions into, like 2 + 3 * 4",
        title="Calculator",
        description="A command-line calculator that reads an expression and prints the result.",
        repo_full_name=CALCULATOR_REPO,
    )
    calculator_tickets = [
        Ticket(
            position=1,
            title="Make add() and subtract() return the right answer",
            why="Every other feature of the calculator builds on these two working correctly.",
            acceptance_criteria=[
                "add(2, 3) returns 5 and subtract(2, 3) returns -1",
                "Works with negative numbers and decimals",
            ],
            skill_areas=[SkillArea.backend, SkillArea.testing],
        ),
        Ticket(
            position=2,
            title="Handle dividing by zero",
            why="Users will try it. A crash with a stack trace is a bad experience and leaks internals.",
            acceptance_criteria=[
                "divide(1, 0) shows a clear error message instead of crashing",
                "Other divisions still work as before",
            ],
            skill_areas=[SkillArea.backend, SkillArea.debugging],
        ),
        Ticket(
            position=3,
            title="Evaluate a whole expression",
            why=(
                "Users type an expression like 2 + 3 * 4 and expect the right answer. "
                "Anything they type reaches your code, so it has to be handled safely."
            ),
            acceptance_criteria=[
                "evaluate('2 + 3 * 4') returns 14 (the usual order of operations)",
                "Invalid input like '2 + + 3' shows an error message",
                "Input is never run as code",
            ],
            skill_areas=[SkillArea.backend, SkillArea.security, SkillArea.debugging],
        ),
    ]

    todo = Project(
        learner_id=learner_id,
        idea="A to-do list that remembers my tasks between runs",
        title="To-do list",
        description="A command-line to-do list you can add to, tick off and keep between runs.",
        repo_full_name=TODO_REPO,
    )
    todo_tickets = [
        Ticket(
            position=1,
            title="Reject blank to-do titles",
            why="A blank item clutters the list and is almost always a mistake.",
            acceptance_criteria=[
                "Adding '' or '   ' shows a message and adds nothing",
                "Normal titles are still added",
            ],
            skill_areas=[SkillArea.backend, SkillArea.testing],
        ),
        Ticket(
            position=2,
            title="Mark an item as done",
            why="Ticking things off is the whole point of a to-do list.",
            acceptance_criteria=[
                "complete(item_id) marks the item done and the list shows it",
                "An unknown item_id shows a clear error",
            ],
            skill_areas=[SkillArea.backend, SkillArea.debugging],
        ),
        Ticket(
            position=3,
            title="Save and load the list between runs",
            why="People expect their list to still be there when they come back.",
            acceptance_criteria=[
                "Items survive closing and reopening the app",
                "A corrupted or missing save file doesn't crash the app",
                "Loading the file never runs code from it",
            ],
            skill_areas=[SkillArea.database, SkillArea.security, SkillArea.debugging],
        ),
    ]
    return [(calculator, calculator_tickets), (todo, todo_tickets)]


STARTING_SKILLS = {area: 0 for area in SkillArea}


def seed(session: Session) -> None:
    # 1. The learner first: their projects need their ID.
    learner = Learner(name="Param Mehta", github_login=settings.demo_learner_github_login)
    session.add(learner)
    session.flush()  # sends the insert so the database assigns learner.id
    assert learner.id is not None

    # 2. Their starting skill map: every area at 0.
    session.add_all(
        SkillScore(learner_id=learner.id, area=area, score=score)
        for area, score in STARTING_SKILLS.items()
    )

    # 3. The demo projects, owned by that learner, each with its tickets.
    for project, tickets in demo_project(learner.id):
        session.add(project)
        session.flush()  # assigns project.id so the tickets can point at it
        for ticket in tickets:
            ticket.project_id = project.id  # type: ignore[assignment]
            session.add(ticket)

    # 4. Save everything at once. If anything above failed, nothing is saved.
    session.commit()


def reset_and_seed() -> None:
    SQLModel.metadata.drop_all(engine)
    create_db()
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    reset_and_seed()
    print("Seeded: 1 learner, 2 demo projects with 6 tickets.")
