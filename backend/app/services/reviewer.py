"""The Claude calls behind the AI senior reviewer.

Every call returns a Pydantic model through `messages.parse`, so the output is
checked against our schema before any of our code touches it.

The API key comes from `config.settings` (backend/.env), falling back to the
ANTHROPIC_API_KEY environment variable.
"""

import logging
from functools import cache
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.models import SkillArea

MODEL = "claude-opus-5-5"

# Claude Opus 5.5 can decline a request on safety grounds. With "default"
# fallbacks the API re-runs a declined request on a suitable model inside the
# same call, so a false positive on security-flavoured code doesn't stall the demo.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Seconds per attempt. The SDK retries once (timeouts, connection errors, 429 and
# 5xx), so the worst case is about twice this before the caller's fallback kicks in.
# Reviewing a small diff takes ~30s, so it gets the longer limit.
TIMEOUT_SECONDS = 60.0
# Tickets take ~15s. The learner is watching a spinner, so this one is shorter:
# with the retry, at most ~40s before the example tickets show.
TICKETS_TIMEOUT_SECONDS = 20.0

# A hint snippet longer than this is getting close to "the corrected code".
MAX_SNIPPET_LINES = 5

# The comprehension gate asks 2-3 questions per push (the brief's number).
MIN_QUESTIONS = 2
MAX_QUESTIONS = 3

# The idea summary on the dashboard card. Claude is asked for the target and the
# result is trimmed to the max, so the card's size is predictable.
SUMMARY_TARGET_CHARS = 400
MAX_SUMMARY_CHARS = 500

# The one rule for every learner in the MVP. It lives in one place so it can
# become one rule per level later.
AI_RULE = (
    "The AI reviews and tutors. It never writes the learner's code: no full "
    "solutions, no corrected versions of their functions, no copy-pasteable fixes."
)



# --- Output shapes (what Claude returns) ---------------------------------------
# These mirror the DB columns in the data model, so saving a result is a copy.


class TicketDraft(BaseModel):
    title: str = Field(description="Short, imperative, e.g. 'Evaluate a whole expression'")
    why: str = Field(description="Why this matters to the user or the codebase. Never how to build it.")
    acceptance_criteria: list[str] = Field(description="3-5 checkable outcomes, phrased as behaviour")
    skill_areas: list[SkillArea] = Field(description="1-3 areas this ticket exercises")


class TicketSet(BaseModel):
    project_title: str
    description: str = Field(
        description=(
            "One paragraph, addressed to the learner, on how you understood their idea: "
            f"who it's for and the core features you inferred. At most {SUMMARY_TARGET_CHARS} "
            "characters. Shown on their dashboard."
        )
    )
    tickets: list[TicketDraft]


class TicketResult(TicketSet):
    """What generate_tickets returns. Not sent to Claude, so Claude never sets the flag."""

    # A hard cap so the dashboard card has a predictable size. generate_tickets
    # trims to it, so this never fails on Claude's output.
    description: str = Field(max_length=MAX_SUMMARY_CHARS)

    # True when Claude was unavailable and these are the cached example tickets.
    # The UI says so and offers "Try again".
    is_fallback: bool


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


class ReviewQuestion(BaseModel):
    text: str = Field(
        description=(
            "A question about a specific line or choice in the learner's own diff, answerable in a "
            "few sentences without running code, e.g. 'What happens if this input is empty?'"
        )
    )
    file: str | None = Field(description="The file the question is about, if it's about one")
    line: int | None = Field(description="Line number in the new version of the file, if it's about one")
    finding_index: int | None = Field(
        description="0-based index into findings if this question is about one of them, else null"
    )


class ReviewResult(BaseModel):
    summary: str = Field(description="2-3 sentences: what the PR does well, then what needs attention")
    findings: list[ReviewFinding]
    questions: list[ReviewQuestion] = Field(
        description=f"{MIN_QUESTIONS}-{MAX_QUESTIONS} comprehension questions about the learner's own diff"
    )
    policy_flags: list[str] = Field(
        description="Ways the PR breaks the AI rule or misses the ticket's scope. Empty if none."
    )


class PreviousFinding(BaseModel):
    """A finding from the review of the PR's previous push, so the next review can see what changed."""

    kind: str
    vuln_class: str | None
    file: str
    line: int | None
    explanation: str


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

First write a one-paragraph description of how you understood the idea: who it's for and the
core features you inferred. The learner reads this to check you understood them, so say plainly
anything you assumed that they didn't state.

- Each ticket explains WHY it matters and lists acceptance criteria as observable behaviour.
- Never explain HOW: no function names, libraries, algorithms, code or step-by-step instructions.
- Spread the tickets across the stack where the idea allows (backend, frontend, database, testing,
  security), so the learner widens their skills instead of repeating one kind of task.
- Put the ticket for the project's core feature (the thing the idea is mainly about) first.
  Later tickets extend it, test it, harden it or add around it. Keep each one small enough
  to finish in a sitting.
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

questions: {MIN_QUESTIONS}-{MAX_QUESTIONS} comprehension questions that check the learner understands their OWN
code: what a line does, why they chose an approach, what happens with an edge case. Point each one
at a file and line where you can. Never ask them to write code, and never put the answer to a
finding in a question. If a previous review is given and this diff fixes one of its findings,
at least one question must ask them to explain how their change fixes it.

policy_flags: note anything that breaks the AI rule (e.g. the PR description says the AI wrote it)
or work clearly outside the ticket. Leave it empty if there's nothing."""


# --- Fallbacks ------------------------------------------------------------------
# Known-good output for when Claude is unavailable during judging. The first
# ticket is the one the demo PR (the eval() trap) is written against.
# These name functions (evaluate(), divide(), CalculatorError), which the tickets
# prompt forbids. That's deliberate: the demo repo already has those functions,
# and the criteria have to match the code the demo PR changes.

FALLBACK_TICKETS = TicketSet(
    project_title="Calculator",
    description=(
        "A command-line calculator for anyone who wants to type a whole sum, like "
        "2 + 3 * 4, and get the answer a maths teacher would give. I assumed it runs "
        "in the terminal, reads one expression at a time, and should never crash on "
        "bad input."
    ),
    tickets=[
        TicketDraft(
            title="Evaluate a whole expression",
            why=(
                "People want to type a whole sum like 2 + 3 * 4 instead of calling one "
                "operation at a time, and get the answer a maths teacher would give."
            ),
            acceptance_criteria=[
                "evaluate('2 + 3 * 4') returns 14, following the order of operations",
                "Brackets and decimals work",
                "Empty or invalid input gives a clear CalculatorError, never a crash",
                "Dividing by zero gives the same clear error as divide()",
            ],
            skill_areas=["backend", "security", "debugging"],
        ),
        TicketDraft(
            title="Prove the calculator works with tests",
            why=(
                "A calculator people can't trust is worse than none. Tests catch the "
                "next change that quietly breaks a sum you already got right."
            ),
            acceptance_criteria=[
                "Running the tests checks order of operations, brackets and decimals",
                "There's a test for each kind of input that should give an error",
                "Breaking evaluate() on purpose makes at least one test fail",
            ],
            skill_areas=["testing", "debugging"],
        ),
        TicketDraft(
            title="Keep a history of past calculations",
            why=(
                "People often need an answer they worked out a few minutes ago, even "
                "after closing the calculator."
            ),
            acceptance_criteria=[
                "Each expression and its result is kept, newest first",
                "The history is still there after closing and reopening the calculator",
                "A missing or corrupted history file doesn't crash the calculator",
                "Loading the history never runs anything stored in it",
            ],
            skill_areas=["database", "security"],
        ),
        TicketDraft(
            title="Use the last answer in the next sum",
            why=(
                "Long calculations happen in steps. Retyping the previous answer is slow "
                "and invites typos."
            ),
            acceptance_criteria=[
                "Typing 'ans' in an expression uses the previous result, e.g. 'ans * 2'",
                "Using 'ans' before any calculation gives a clear error",
                "An expression that fails leaves the previous 'ans' unchanged",
            ],
            skill_areas=["backend", "debugging"],
        ),
    ],
)


# --- Calls ----------------------------------------------------------------------

logger = logging.getLogger(__name__)

# 400 bad request, 401 bad key, 403 no access, 404 wrong model name: our problem,
# unlike timeouts, 429 or 5xx.
_OUR_FAULT_STATUSES = {400, 401, 403, 404}

@cache
def _client() -> anthropic.Anthropic:
    # Created on first use, not at import, so importing this module (e.g. in tests)
    # doesn't need an API key.
    # None lets the SDK fall back to the ANTHROPIC_API_KEY environment variable.
    key = settings.anthropic_api_key
    return anthropic.Anthropic(
        api_key=key.get_secret_value() if key else None,
        timeout=TIMEOUT_SECONDS,
        max_retries=1,
    )


def _parse(
    system: str,
    messages: list[dict],
    output_format: type[BaseModel],
    effort: str,
    timeout: float = TIMEOUT_SECONDS,
):
    """One structured call with refusal handling. Returns the parsed model."""
    try:
        response = _client().beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=messages,
            output_format=output_format,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
            timeout=timeout,
        )
    except anthropic.APITimeoutError as e:
        raise ReviewerError("Claude timed out") from e
    except anthropic.APIStatusError as e:
        if e.status_code in _OUR_FAULT_STATUSES:
            # A bad key or a bad request won't fix itself, so make it loud, not just
            # a fallback. Only the status goes in the log, never the key.
            logger.error("Claude API error %s: check the API key and the request", e.status_code)
        raise ReviewerError(f"Claude API error {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise ReviewerError("Couldn't reach Claude") from e
    except ValidationError as e:
        # parse() validates Claude's JSON inside the call, so a cut-off or malformed
        # answer raises here, before the stop_reason checks below can run.
        raise ReviewerError("Claude's answer didn't match the schema") from e

    if response.stop_reason == "refusal":
        category = response.stop_details.category if response.stop_details else None
        raise ReviewerError(f"Claude declined the request (category: {category})")
    if response.stop_reason == "max_tokens":
        raise ReviewerError("Claude's answer was cut off")
    if response.parsed_output is None:
        raise ReviewerError("Claude's answer didn't match the schema")
    return response.parsed_output


def _tickets_from_claude(idea: str) -> TicketSet:
    result = _parse(
        TICKETS_SYSTEM,
        [{"role": "user", "content": f"My project idea:\n\n{idea}"}],
        TicketSet,
        effort="medium",
        timeout=TICKETS_TIMEOUT_SECONDS,
    )
    if not 3 <= len(result.tickets) <= 5:
        raise ReviewerError(f"Expected 3-5 tickets, got {len(result.tickets)}")
    return result


def generate_tickets(idea: str) -> TicketResult:
    """Turn a learner's project idea into 3-5 tickets: the why, never the how.

    Never raises for a Claude problem: if Claude is slow, down or declines, it
    returns the cached calculator tickets with is_fallback=True, so the demo
    always has a project to work on.
    """
    try:
        result = _tickets_from_claude(idea)
    except ReviewerError as e:
        # The message is ours (no key or request content), so it's safe to log.
        logger.warning("generate_tickets fell back to the cached tickets: %s", e)
        return _fallback()
    except Exception:
        # Last resort: this function promises never to raise for a Claude problem,
        # so an error we didn't foresee still gives the demo its tickets.
        logger.exception("generate_tickets hit an unexpected error, using the cached tickets")
        return _fallback()
    data = result.model_dump()
    data["description"] = _trim_summary(data["description"])
    return TicketResult(**data, is_fallback=False)


def _fallback() -> TicketResult:
    return TicketResult(**FALLBACK_TICKETS.model_dump(), is_fallback=True)


def _trim_summary(text: str) -> str:
    """Keep the summary within MAX_SUMMARY_CHARS, cut at a sentence end where possible.

    The prompt asks for less, so this rarely runs. Trimming beats failing over to
    the example tickets just because the summary ran long.
    """
    text = text.strip()
    if len(text) <= MAX_SUMMARY_CHARS:
        return text
    cut = text[:MAX_SUMMARY_CHARS]
    end = cut.rfind(". ")
    if end > MAX_SUMMARY_CHARS // 2:
        return cut[: end + 1]
    return cut[: MAX_SUMMARY_CHARS - 1].rstrip() + "…"


def _long_snippets(review: ReviewResult) -> list[ReviewFinding]:
    return [
        f for f in review.findings
        if len(f.hints.snippet.strip().splitlines()) > MAX_SNIPPET_LINES
    ]


def review_diff(diff: str, ticket: TicketContext, previous: list[PreviousFinding] | None = None) -> ReviewResult:
    """Socratic + security review of a learner's PR diff against its ticket, plus the
    comprehension questions for the gate.

    `previous` is the last push's findings, so the review can tell what got fixed and ask
    the learner to explain the fix.

    A snippet over MAX_SNIPPET_LINES gets one retry with a reminder. If it's still
    too long, we fail rather than risk posting corrected code.
    """
    criteria = "\n".join(f"- {c}" for c in ticket.acceptance_criteria)
    messages = [{
        "role": "user",
        "content": (
            f"<ticket>\nTitle: {ticket.title}\nWhy: {ticket.why}\n"
            f"Acceptance criteria:\n{criteria}\n</ticket>\n\n"
            f"{_previous_block(previous)}"
            f"<diff>\n{diff}\n</diff>"
        ),
    }]

    review = _parse(REVIEW_SYSTEM, messages, ReviewResult, effort="high")
    too_long = _long_snippets(review)
    if not too_long:
        return _check_questions(review)

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
    return _check_questions(review)


def _previous_block(previous: list[PreviousFinding] | None) -> str:
    if not previous:
        return ""
    lines = [
        f"- [{f.kind}] {f.vuln_class or 'correctness'} at {f.file}:{f.line}: {f.explanation}"
        for f in previous
    ]
    return "<previous_review>\nFindings on the learner's previous push:\n" + "\n".join(lines) + "\n</previous_review>\n\n"


def _check_questions(review: ReviewResult) -> ReviewResult:
    """At most MAX_QUESTIONS, and finding_index only where it points at a real finding.

    Fewer than MIN_QUESTIONS is still usable, but none means the gate has nothing to ask.
    """
    if not review.questions:
        raise ReviewerError("The review came back with no comprehension questions")
    questions = review.questions[:MAX_QUESTIONS]
    for q in questions:
        if q.finding_index is not None and not 0 <= q.finding_index < len(review.findings):
            q.finding_index = None
    return review.model_copy(update={"questions": questions})
