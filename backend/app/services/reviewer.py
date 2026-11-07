"""The Claude calls behind the AI senior reviewer.

Every call returns a Pydantic model through `messages.parse`, so the output is
checked against our schema before any of our code touches it.

This file is standalone on purpose: it doesn't import `models.py` or `config.py`
yet, so it can be built and tested before the backend skeleton (PR #2) lands.
The Anthropic SDK reads ANTHROPIC_API_KEY from the environment by itself.
"""

from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"

# Claude Opus 5.5 can decline a request on safety grounds. With "default"
# fallbacks the API re-runs a declined request on a suitable model inside the
# same call, so a false positive on security-flavoured code doesn't stall the demo.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Seconds per request. Claude reviewing a small diff takes well under this; if it
# doesn't answer in time the caller uses the cached demo output instead.
TIMEOUT_SECONDS = 60.0

# A hint snippet longer than this is getting close to "the corrected code".
MAX_SNIPPET_LINES = 5

# The one rule for every learner in the MVP. It lives in one place so it can
# become one rule per level later.
AI_RULE = (
    "The AI reviews and tutors. It never writes the learner's code: no full "
    "solutions, no corrected versions of their functions, no copy-pasteable fixes."
)

# Matches SkillArea in models.py (PR #2). Switch to importing it once that merges.
SkillAreaName = Literal[
    "frontend", "backend", "database", "git", "debugging", "security", "testing"
]


# --- Output shapes (what Claude returns) ---------------------------------------
# These mirror the DB columns in the data model, so saving a result is a copy.


class TicketDraft(BaseModel):
    title: str = Field(description="Short, imperative, e.g. 'Evaluate a whole expression'")
    why: str = Field(description="Why this matters to the user or the codebase. Never how to build it.")
    acceptance_criteria: list[str] = Field(description="3-5 checkable outcomes, phrased as behaviour")
    skill_areas: list[SkillAreaName] = Field(description="1-3 areas this ticket exercises")


class TicketSet(BaseModel):
    project_title: str
    tickets: list[TicketDraft]


class HintLadder(BaseModel):
    concept: str = Field(description="Rung 1: the general idea or vulnerability class, no reference to their code")
    where_to_look: str = Field(description="Rung 2: point at the file, line or construct, without saying what to change")
    snippet: str = Field(
        description=(
            f"Rung 3: at most {MAX_SNIPPET_LINES} lines illustrating the technique on a "
            "DIFFERENT example than the learner's code. Never their fixed function."
        )
    )


class ReviewFinding(BaseModel):
    kind: Literal["security", "correctness"]
    vuln_class: str | None = Field(
        description="For security findings, the class and CWE, e.g. 'Code injection (CWE-94)'. Null for correctness."
    )
    file: str
    line: int | None = Field(description="Line number in the new version of the file")
    explanation: str = Field(description="What goes wrong and why it matters, in plain words for a beginner")
    socratic_question: str = Field(description="A question that leads the learner to find the problem themselves")
    hints: HintLadder


class ReviewResult(BaseModel):
    summary: str = Field(description="2-3 sentences: what the PR does well, then what needs attention")
    findings: list[ReviewFinding]
    policy_flags: list[str] = Field(
        description="Ways the PR breaks the AI rule or misses the ticket's scope. Empty if none."
    )


class TicketContext(BaseModel):
    """The ticket a PR is for, as the reviewer needs it."""

    title: str
    why: str
    acceptance_criteria: list[str]


# --- Errors ---------------------------------------------------------------------


class ReviewerError(Exception):
    """Claude couldn't produce a usable result. The caller should use its fallback."""


# --- Prompts --------------------------------------------------------------------

TICKETS_SYSTEM = f"""You write tickets for a learner who is new to software engineering.

{AI_RULE}

Turn the learner's project idea into 3-5 tickets that together build a small, working version of it.

- Each ticket explains WHY it matters and lists acceptance criteria as observable behaviour.
- Never explain HOW: no function names, libraries, algorithms, code or step-by-step instructions.
- Spread the tickets across the stack where the idea allows (backend, frontend, database, testing,
  security), so the learner widens their skills instead of repeating one kind of task.
- Order them so each one builds on the last. The first should be achievable in under an hour.
- Where the idea takes user input, include at least one acceptance criterion about bad or
  malicious input, so security is part of "done"."""

REVIEW_SYSTEM = f"""You are a senior engineer reviewing a pull request from a learner who is new to programming.

{AI_RULE}

Your job is to make them understand their own code, not to fix it for them.

Look for:
- Security problems: injection of any kind (code, SQL, command), hardcoded secrets, missing
  authentication or authorization, unvalidated input, unsafe dependencies.
- Correctness problems: crashes, unhandled errors, edge cases the ticket's acceptance criteria
  care about, and tests that pass without proving the behaviour.

Report each real problem as a finding. Report every problem you're confident about, most severe
first. Don't pad the list with style nitpicks.

For each finding:
- explanation: what goes wrong and why it matters, in plain words.
- socratic_question: a question that leads them to discover the problem, e.g. "What happens if
  someone types X here?". Don't give the answer in the question.
- hints: a ladder from vague to specific. The snippet rung shows the technique on a different,
  small example (at most {MAX_SNIPPET_LINES} lines). It must never be a corrected version of their code.

Line numbers refer to the new version of the file, counted from the diff's @@ headers.

policy_flags: note anything that breaks the AI rule (e.g. the PR description says the AI wrote it)
or work clearly outside the ticket. Leave it empty if there's nothing."""


# --- Calls ----------------------------------------------------------------------

_client = anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=1)


def _parse(system: str, messages: list[dict], output_format: type[BaseModel], effort: str):
    """One structured call with refusal handling. Returns the parsed model."""
    try:
        response = _client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=messages,
            output_format=output_format,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APITimeoutError as e:
        raise ReviewerError("Claude timed out") from e
    except anthropic.APIStatusError as e:
        raise ReviewerError(f"Claude API error {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise ReviewerError("Couldn't reach Claude") from e

    if response.stop_reason == "refusal":
        category = response.stop_details.category if response.stop_details else None
        raise ReviewerError(f"Claude declined the request (category: {category})")
    if response.stop_reason == "max_tokens":
        raise ReviewerError("Claude's answer was cut off")
    if response.parsed_output is None:
        raise ReviewerError("Claude's answer didn't match the schema")
    return response.parsed_output


def generate_tickets(idea: str) -> TicketSet:
    """Turn a learner's project idea into 3-5 tickets: the why, never the how."""
    result = _parse(
        TICKETS_SYSTEM,
        [{"role": "user", "content": f"My project idea:\n\n{idea}"}],
        TicketSet,
        effort="medium",
    )
    if not 3 <= len(result.tickets) <= 5:
        raise ReviewerError(f"Expected 3-5 tickets, got {len(result.tickets)}")
    return result


def _long_snippets(review: ReviewResult) -> list[ReviewFinding]:
    return [
        f for f in review.findings
        if len(f.hints.snippet.strip().splitlines()) > MAX_SNIPPET_LINES
    ]


def review_diff(diff: str, ticket: TicketContext) -> ReviewResult:
    """Socratic + security review of a learner's PR diff against its ticket.

    A snippet over MAX_SNIPPET_LINES gets one retry with a reminder. If it's still
    too long, we fail rather than risk posting corrected code.
    """
    criteria = "\n".join(f"- {c}" for c in ticket.acceptance_criteria)
    messages = [{
        "role": "user",
        "content": (
            f"<ticket>\nTitle: {ticket.title}\nWhy: {ticket.why}\n"
            f"Acceptance criteria:\n{criteria}\n</ticket>\n\n"
            f"<diff>\n{diff}\n</diff>"
        ),
    }]

    review = _parse(REVIEW_SYSTEM, messages, ReviewResult, effort="high")
    too_long = _long_snippets(review)
    if not too_long:
        return review

    # One retry: show Claude its own answer and say exactly what to shorten.
    files = ", ".join(sorted({f"{f.file}:{f.line}" for f in too_long}))
    messages += [
        {"role": "assistant", "content": review.model_dump_json()},
        {
            "role": "user",
            "content": (
                f"The snippet hints for {files} are longer than {MAX_SNIPPET_LINES} lines. "
                "Redo the review with every snippet at most "
                f"{MAX_SNIPPET_LINES} lines, on a different example than my code."
            ),
        },
    ]
    review = _parse(REVIEW_SYSTEM, messages, ReviewResult, effort="high")
    if _long_snippets(review):
        raise ReviewerError("Hint snippets were still too long after a retry")
    return review
