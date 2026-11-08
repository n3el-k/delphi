"""Run the reviewer's Claude calls against the demo calculator and print the results.

Run from backend/:

    uv run python -m scripts.try_reviewer
    uv run python -m scripts.try_reviewer review

It makes real API calls, so each run costs a little.
"""

import logging
import sys
import time
from pathlib import Path

from app.services.reviewer import TicketContext, generate_tickets, review_diff

DIFF = Path(__file__).parent.parent / "tests" / "fixtures" / "eval_pr.diff"

CALCULATOR_IDEA = "A command-line calculator that reads an expression like 2 + 3 * 4 and prints the result."

# The expression ticket the demo PR is written against. It names evaluate() and
# CalculatorError, which real tickets never do, because the demo repo already has them.
EXPRESSION_TICKET = TicketContext(
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
)


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
        timed("tickets", generate_tickets, CALCULATOR_IDEA)
    if which in ("all", "review"):
        review = timed("review", review_diff, DIFF.read_text(), EXPRESSION_TICKET)
        classes = [f.vuln_class or f.kind for f in review.findings]
        print("\nFindings:", classes)
        print("Caught code injection:", any("94" in c or "injection" in c.lower() for c in classes))
        print(f"Questions ({len(review.questions)}):")
        for q in review.questions:
            print(f"  - [{q.file}:{q.line}, finding {q.finding_index}] {q.text}")


if __name__ == "__main__":
    main()
