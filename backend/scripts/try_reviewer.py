"""Run the reviewer's Claude calls against the demo calculator and print the results.

Run from backend/:

    uv run --env-file .env python -m scripts.try_reviewer
    uv run --env-file .env python -m scripts.try_reviewer review

It makes real API calls, so each run costs a little.
"""

import logging
import sys
import time
from pathlib import Path

from app.services.reviewer import FALLBACK_TICKETS, TicketContext, generate_tickets, review_diff

DIFF = Path(__file__).parent.parent / "tests" / "fixtures" / "eval_pr.diff"

CALCULATOR_IDEA = "A command-line calculator that reads an expression like 2 + 3 * 4 and prints the result."

# The expression ticket the demo PR is written against: the fallback's first ticket.
EXPRESSION_TICKET = TicketContext(**FALLBACK_TICKETS.tickets[0].model_dump(exclude={"skill_areas"}))


def timed(label, fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    print(f"\n=== {label} ({time.perf_counter() - start:.1f}s) ===")
    print(result.model_dump_json(indent=2))
    return result


def main():
    logging.basicConfig(level=logging.WARNING)
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "tickets"):
        tickets = timed("tickets", generate_tickets, CALCULATOR_IDEA)
        if tickets.is_fallback:
            print("\nClaude was unavailable: these are the cached fallback tickets (see the warning above).")
    if which in ("all", "review"):
        review = timed("review", review_diff, DIFF.read_text(), EXPRESSION_TICKET)
        classes = [f.vuln_class or f.kind for f in review.findings]
        print("\nFindings:", classes)
        print("Caught code injection:", any("94" in c or "injection" in c.lower() for c in classes))


if __name__ == "__main__":
    main()
