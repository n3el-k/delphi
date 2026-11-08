"""Tests for the reviewer's fallback behaviour. No real Claude calls: _parse is replaced."""

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


def test_fallback_puts_the_expression_ticket_first() -> None:
    # The demo PR is written against this ticket, and "first not done" must land on it.
    assert FALLBACK_TICKETS.tickets[0].title == "Evaluate a whole expression"
    assert 3 <= len(FALLBACK_TICKETS.tickets) <= 5
