"""Tests for the reviewer's fallback behaviour. No real Claude calls: _parse is replaced."""

import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.services import reviewer
from app.services.reviewer import FALLBACK_TICKETS, ReviewerError, TicketDraft, TicketSet


def fail(*_args, **_kwargs):
    raise ReviewerError("Claude timed out")


def test_falls_back_to_cached_tickets_when_claude_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reviewer, "_parse", fail)
    result = reviewer.generate_tickets("A calculator")
    assert result.is_fallback is True
    assert result.tickets == FALLBACK_TICKETS.tickets


def test_falls_back_when_claude_returns_too_few_tickets(monkeypatch: pytest.MonkeyPatch) -> None:
    one_ticket = TicketSet(project_title="X", description="Y", tickets=FALLBACK_TICKETS.tickets[:1])
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: one_ticket)
    assert reviewer.generate_tickets("A calculator").is_fallback is True


def test_claude_tickets_are_not_marked_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    good = TicketSet(
        project_title="To-do list",
        description="A to-do list.",
        tickets=[TicketDraft(title=f"T{i}", why="w", acceptance_criteria=["a"], skill_areas=["backend"]) for i in range(3)],
    )
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: good)
    result = reviewer.generate_tickets("A to-do list")
    assert result.is_fallback is False
    assert result.project_title == "To-do list"


def test_ticket_calls_use_the_shorter_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def spy(*_args, timeout, **_kwargs):
        seen["timeout"] = timeout
        raise ReviewerError("stop")

    monkeypatch.setattr(reviewer, "_parse", spy)
    reviewer.generate_tickets("A calculator")
    assert seen["timeout"] == reviewer.TICKETS_TIMEOUT_SECONDS


class FakeClient:
    """Stands in for anthropic.Anthropic: client.beta.messages.parse runs `parse`."""

    def __init__(self, parse):
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=parse))


def use_client(monkeypatch: pytest.MonkeyPatch, parse) -> None:
    monkeypatch.setattr(reviewer, "_client", lambda: FakeClient(parse))


def test_cut_off_json_falls_back_instead_of_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    # parse() validates Claude's JSON inside the call, so a cut-off answer raises
    # pydantic's ValidationError, not an Anthropic error.
    def cut_off(**_kwargs):
        TicketSet.model_validate_json('{"project_title": "Calc", "description": "A calc')

    use_client(monkeypatch, cut_off)
    with pytest.raises(ReviewerError):  # _parse turns it into our error, not the last-resort catch
        reviewer._parse("system", [], TicketSet, effort="low")
    assert reviewer.generate_tickets("A calculator").is_fallback is True


def test_unexpected_errors_still_fall_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(**_kwargs):
        raise RuntimeError("something we didn't foresee")

    use_client(monkeypatch, boom)
    assert reviewer.generate_tickets("A calculator").is_fallback is True


def test_a_bad_key_is_logged_as_an_error(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def unauthorized(**_kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.AuthenticationError(
            "invalid x-api-key", response=httpx.Response(401, request=request), body=None
        )

    use_client(monkeypatch, unauthorized)
    with caplog.at_level(logging.WARNING):
        assert reviewer.generate_tickets("A calculator").is_fallback is True
    assert any(r.levelno == logging.ERROR and "401" in r.getMessage() for r in caplog.records)


def test_a_long_summary_is_trimmed_at_a_sentence(monkeypatch: pytest.MonkeyPatch) -> None:
    sentence = "This sentence is exactly fifty characters long ok. "
    long = TicketSet(project_title="X", description=sentence * 20, tickets=FALLBACK_TICKETS.tickets)
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: long)
    result = reviewer.generate_tickets("An idea")
    assert result.is_fallback is False
    assert len(result.description) <= reviewer.MAX_SUMMARY_CHARS
    assert result.description.endswith(".")


def test_fallback_puts_the_expression_ticket_first() -> None:
    # The demo PR is written against this ticket, and "first not done" must land on it.
    assert FALLBACK_TICKETS.tickets[0].title == "Evaluate a whole expression"
    assert 3 <= len(FALLBACK_TICKETS.tickets) <= 5


# --- Comprehension questions in the review -------------------------------------


def _review(questions: list[reviewer.ReviewQuestion], findings: int = 1) -> reviewer.ReviewResult:
    finding = reviewer.ReviewFinding(
        kind="security", vuln_class="Code injection (CWE-94)", file="calculator.py", line=32,
        explanation="eval runs any code.", socratic_question="What else would eval run?",
        hints=reviewer.HintLadder(concept="c", where_to_look="w", snippet="s"),
    )
    return reviewer.ReviewResult(summary="s", findings=[finding] * findings, questions=questions, policy_flags=[])


def _question(index: int | None = None) -> reviewer.ReviewQuestion:
    return reviewer.ReviewQuestion(text="Why?", file="calculator.py", line=1, finding_index=index)


TICKET = reviewer.TicketContext(title="t", why="w", acceptance_criteria=["a"])


def test_review_keeps_at_most_three_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: _review([_question()] * 5))
    assert len(reviewer.review_diff("diff", TICKET).questions) == reviewer.MAX_QUESTIONS


def test_a_question_pointing_at_no_finding_is_unlinked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: _review([_question(0), _question(7)]))
    assert [q.finding_index for q in reviewer.review_diff("diff", TICKET).questions] == [0, None]


def test_a_review_without_questions_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reviewer, "_parse", lambda *a, **k: _review([]))
    with pytest.raises(ReviewerError):
        reviewer.review_diff("diff", TICKET)


def test_the_previous_push_findings_go_in_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def parse(system, messages, *args, **kwargs):
        seen["prompt"] = messages[0]["content"]
        return _review([_question()])

    monkeypatch.setattr(reviewer, "_parse", parse)
    previous = reviewer.PreviousFinding(
        kind="security", vuln_class="Code injection (CWE-94)", file="calculator.py", line=32, explanation="eval runs any code."
    )
    reviewer.review_diff("diff", TICKET, [previous])
    assert "<previous_review>" in seen["prompt"]
    assert "Code injection (CWE-94) at calculator.py:32" in seen["prompt"]

    reviewer.review_diff("diff", TICKET)
    assert "<previous_review>" not in seen["prompt"]
