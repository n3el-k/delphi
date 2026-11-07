"""Seed data: the 4 levels, Level 1's projects and tickets, and one learner.

Run with `uv run python -m app.seed`. It wipes the database and starts fresh.
The learner starts brand new: no fake history. All progress comes from real PRs.
"""

from sqlmodel import Session, SQLModel

from app.config import settings
from app.db import create_db, engine
from app.models import Learner, Level, Project, SkillArea, SkillScore, Ticket, TicketSize

# Practice repos the learner opens PRs on (Python). Neel's GitHub App watches these.
# Update once Neel has created them.
CALCULATOR_REPO = "n3el-k/level1-calculator"
TODO_REPO = "n3el-k/level1-todo"


def levels() -> list[Level]:
    return [
        Level(
            number=1,
            name="Foundations",
            ai_policy="No AI code generation. The AI only reviews your PRs and tutors you with questions and hints.",
            starts_at=TicketSize.snippet,
            ends_at=TicketSize.function,
            review_focus="Do you understand each line you wrote: its inputs, edge cases and errors?",
            unlocks=[
                "Socratic AI review on every pull request",
                "Security review of your code",
                "Comprehension gates on your own diff",
            ],
            required_projects=2,
            min_gate_score=70,
            required_security_fixes=1,
        ),
        Level(
            number=2,
            name="Building blocks",
            ai_policy="The AI explains concepts and answers your questions, but still writes no code for you.",
            starts_at=TicketSize.function,
            ends_at=TicketSize.file,
            review_focus="How your functions fit together in a file: structure, naming and error handling.",
            unlocks=[
                "Ask the AI to explain concepts",
                "Tickets that ask for a whole file",
            ],
            required_projects=2,
            min_gate_score=75,
            required_security_fixes=2,
        ),
        Level(
            number=3,
            name="AI for grunt work",
            ai_policy=(
                "The AI may write DELEGABLE tickets (tests, boilerplate, styling, config). "
                "You write every CORE ticket and must explain any AI code you merge."
            ),
            starts_at=TicketSize.file,
            ends_at=TicketSize.delegated,
            review_focus="Your core code and the AI's grunt work: can you explain and critique what the AI wrote?",
            unlocks=[
                "AI code generation on DELEGABLE tickets",
                "Larger projects split into CORE and DELEGABLE work",
            ],
            required_projects=3,
            min_gate_score=80,
            required_security_fixes=3,
        ),
        Level(
            number=4,
            name="Directing agents",
            ai_policy=(
                "You design the architecture and own the core. "
                "Coding agents build the delegable layers, and you review everything they write."
            ),
            starts_at=TicketSize.delegated,
            ends_at=TicketSize.system,
            review_focus="Your architecture and the agents' output against it: trade-offs, and what you rejected.",
            unlocks=[
                "Coding agents for delegable layers",
                "Own the architecture of a whole project",
            ],
            required_projects=3,
            min_gate_score=85,
            required_security_fixes=4,
        ),
    ]


def level1_projects(level_id: int) -> list[tuple[Project, list[Ticket]]]:
    """Level 1 ramps from a few lines (snippet) up to a whole function."""
    calculator = Project(
        level_id=level_id,
        position=1,
        title="Calculator",
        description="A command-line calculator that reads an expression and prints the result.",
        repo_full_name=CALCULATOR_REPO,
    )
    calculator_tickets = [
        Ticket(
            position=1,
            size=TicketSize.snippet,
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
            size=TicketSize.snippet,
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
            size=TicketSize.function,
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
        level_id=level_id,
        position=2,
        title="To-do list",
        description="A command-line to-do list you can add to, tick off and keep between runs.",
        repo_full_name=TODO_REPO,
    )
    todo_tickets = [
        Ticket(
            position=1,
            size=TicketSize.snippet,
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
            size=TicketSize.function,
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
            size=TicketSize.function,
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
    all_levels = levels()
    session.add_all(all_levels)
    session.flush()  # assigns IDs so the projects below can point at Level 1
    level1 = all_levels[0]
    assert level1.id is not None

    for project, tickets in level1_projects(level1.id):
        session.add(project)
        session.flush()
        for ticket in tickets:
            ticket.project_id = project.id  # type: ignore[assignment]
            session.add(ticket)

    learner = Learner(
        name="Param Mehta",
        github_login=settings.demo_learner_github_login,
        current_level_id=level1.id,
    )
    session.add(learner)
    session.flush()
    session.add_all(
        SkillScore(learner_id=learner.id, area=area, score=score)  # type: ignore[arg-type]
        for area, score in STARTING_SKILLS.items()
    )
    session.commit()


def reset_and_seed() -> None:
    SQLModel.metadata.drop_all(engine)
    create_db()
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    reset_and_seed()
    print("Seeded: 4 levels, 2 Level 1 projects with 6 tickets, 1 learner.")
