"""Neel's comprehension gate endpoints: /api/gates/{id}, and flagging a review.

A gate belongs to one PR. It always shows the latest push: that push's review, findings
and questions. Earlier pushes' questions and answers stay in the DB as history.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import (
    Answer,
    Finding,
    Flag,
    FindingKind,
    Gate,
    GateStatus,
    Question,
    Review,
    Submission,
    SubmissionStatus,
    Ticket,
)
from app.schemas import (
    AnswerOut,
    AnswerResult,
    AnswersIn,
    AnswersOut,
    FindingOut,
    FlagIn,
    FlagOut,
    GateOut,
    GateReviewOut,
    QuestionOut,
)
from app.services import github, progress, reviewer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["gates"])


def get_gate(session: Session, gate_id: int) -> tuple[Gate, Submission]:
    gate = session.get(Gate, gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="Gate not found")
    submission = session.get(Submission, gate.submission_id)
    assert submission is not None  # guaranteed by the foreign key
    return gate, submission


def latest_review(session: Session, submission_id: int) -> Review | None:
    return session.exec(
        select(Review).where(Review.submission_id == submission_id).order_by(col(Review.id).desc())
    ).first()


def review_findings(session: Session, review_id: int) -> list[Finding]:
    return list(session.exec(select(Finding).where(Finding.review_id == review_id).order_by(col(Finding.id))).all())


def review_questions(session: Session, gate_id: int, review_id: int) -> list[Question]:
    return list(
        session.exec(
            select(Question).where(Question.gate_id == gate_id, Question.review_id == review_id).order_by(col(Question.id))
        ).all()
    )


def last_answer(session: Session, question_id: int) -> Answer | None:
    return session.exec(
        select(Answer).where(Answer.question_id == question_id).order_by(col(Answer.id).desc())
    ).first()


@router.get("/gates/{gate_id}")
def read_gate(gate_id: int, session: Session = Depends(get_session)) -> GateOut:
    gate, submission = get_gate(session, gate_id)
    ticket = session.get(Ticket, submission.ticket_id)
    assert ticket is not None
    review = latest_review(session, submission.id)  # type: ignore[arg-type]

    findings: list[FindingOut] = []
    questions: list[QuestionOut] = []
    if review is not None:
        findings = [
            FindingOut(
                id=f.id,  # type: ignore[arg-type]
                kind=f.kind,
                vuln_class=f.vuln_class,
                file=f.file,
                line=f.line,
                explanation=f.explanation,
                socratic_question=f.socratic_question,
                hints=f.hints[: f.hints_revealed],
                resolved=f.resolved,
            )
            for f in review_findings(session, review.id)  # type: ignore[arg-type]
        ]
        for q in review_questions(session, gate.id, review.id):  # type: ignore[arg-type]
            answer = last_answer(session, q.id)  # type: ignore[arg-type]
            questions.append(
                QuestionOut(
                    id=q.id,  # type: ignore[arg-type]
                    text=q.text,
                    file=q.file,
                    line=q.line,
                    last_answer=AnswerOut(
                        id=answer.id,  # type: ignore[arg-type]
                        text=answer.text,
                        score=answer.score,
                        passed=answer.passed,
                        explanation=answer.explanation,
                        next_hint=answer.next_hint,
                    )
                    if answer
                    else None,
                )
            )

    return GateOut(
        id=gate.id,  # type: ignore[arg-type]
        status=gate.status,
        pr_url=submission.pr_url,
        ticket_title=ticket.title,
        review=GateReviewOut(id=review.id, summary=review.summary, is_fallback=review.is_fallback)  # type: ignore[arg-type]
        if review
        else None,
        findings=findings,
        questions=questions,
    )


# --- POST /api/gates/{id}/answers ----------------------------------------------


@router.post("/gates/{gate_id}/answers")
def submit_answers(gate_id: int, body: AnswersIn, session: Session = Depends(get_session)) -> AnswersOut:
    """Grade a batch of answers. Pass every question on the latest push and the PR is approved.

    A plain `def`, not `async def`: grading blocks on Claude, so FastAPI runs it in a thread.
    """
    gate, submission = get_gate(session, gate_id)
    if gate.status == GateStatus.reviewing:
        raise HTTPException(status_code=409, detail="The review is still running. Try again in a moment.")
    if gate.status == GateStatus.passed:
        raise HTTPException(status_code=409, detail="This gate has already been passed.")
    review = latest_review(session, submission.id)  # type: ignore[arg-type]
    assert review is not None  # an open gate always has a review
    findings = review_findings(session, review.id)  # type: ignore[arg-type]
    if any(f.kind == FindingKind.security and not f.resolved for f in findings):
        # The brief: a security issue gets fixed and explained, not answered around.
        raise HTTPException(status_code=409, detail="Fix the security finding and push again first.")

    questions = {q.id: q for q in review_questions(session, gate.id, review.id)}  # type: ignore[arg-type]
    ids = [a.question_id for a in body.answers]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="Each question can only be answered once per batch.")
    unknown = [i for i in ids if i not in questions]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Not a question on this gate's latest push: {unknown}")

    # Grade in parallel, so three answers take about as long as one.
    try:
        with ThreadPoolExecutor(max_workers=len(body.answers)) as pool:
            grades = list(
                pool.map(
                    lambda a: reviewer.grade_answer(
                        questions[a.question_id].text, questions[a.question_id].file,
                        questions[a.question_id].line, submission.diff, a.text,
                    ),
                    body.answers,
                )
            )
    except reviewer.ReviewerError as e:
        # Nothing is saved, so the learner just tries again. A failed grade never counts against them.
        logger.error("Grading failed for gate %s: %s", gate_id, e)
        raise HTTPException(status_code=503, detail="Grading is unavailable right now. Please try again.") from None

    by_id = {f.id: f for f in findings}
    results = []
    for a, grade in zip(body.answers, grades):
        passed = grade.score >= reviewer.PASS_SCORE
        next_hint = None if passed else _next_hint(by_id.get(questions[a.question_id].finding_id), grade.next_hint)
        row = Answer(
            question_id=a.question_id, text=a.text, score=grade.score, passed=passed,
            explanation=grade.explanation, next_hint=next_hint,
        )
        session.add(row)
        session.flush()  # gives the answer its id for the response
        results.append(
            AnswerResult(
                question_id=a.question_id, answer_id=row.id, score=grade.score, passed=passed,  # type: ignore[arg-type]
                explanation=grade.explanation, next_hint=next_hint,
            )
        )
    session.commit()

    gate_passed = all(
        (latest := last_answer(session, qid)) is not None and latest.passed for qid in questions
    )
    if gate_passed:
        _pass_gate(session, gate, submission, review)
    return AnswersOut(passed=gate_passed, results=results)


def _next_hint(finding: Finding | None, grader_hint: str) -> str | None:
    """A failed answer about a finding climbs that finding's hint ladder:
    concept → where to look → snippet. Past the top, or with no finding, the grader's hint."""
    if finding is not None and finding.hints_revealed < len(finding.hints):
        finding.hints_revealed += 1
        return finding.hints[finding.hints_revealed - 1]
    return grader_hint or None


def _pass_gate(session: Session, gate: Gate, submission: Submission, review: Review) -> None:
    """Approve the PR, mark fixed findings resolved, then hand over to Param's progress code."""
    gate.status = GateStatus.passed  # passed_at is left to progress.record_gate_pass
    submission.status = SubmissionStatus.approved
    _resolve_fixed_findings(session, submission.id, review)  # type: ignore[arg-type]
    session.add_all([gate, submission])
    session.commit()

    try:
        github.approve_pr(
            submission.repo_full_name, submission.pr_number, submission.head_sha,
            "You explained your code and every question passed. Approved. Nice work.",
        )
    except github.GitHubError as e:
        # The learner earned the pass, so it stands. The approval can be redone by hand.
        logger.error("Couldn't approve PR %s#%s: %s", submission.repo_full_name, submission.pr_number, e)

    progress.record_gate_pass(session, submission.learner_id, submission.id)  # type: ignore[arg-type]


CWE = re.compile(r"CWE-(\d+)")


def _finding_key(f: Finding) -> tuple[str, str, str | None]:
    """What makes two findings "the same problem" across pushes. Claude words the class
    differently each time ("CWE-95: Eval injection" vs "CWE-95"), so only the CWE number counts."""
    match = CWE.search(f.vuln_class or "")
    return (f.kind, f.file, match.group(1) if match else None)


def _resolve_fixed_findings(session: Session, submission_id: int, latest: Review) -> None:
    """A finding from an earlier push that the latest review no longer reports was fixed.

    Only the newest copy of each problem is marked, so a bug reported on three pushes is
    one fix, not three.
    """
    still_there = {_finding_key(f) for f in review_findings(session, latest.id)}  # type: ignore[arg-type]
    earlier = session.exec(
        select(Finding)
        .join(Review, col(Finding.review_id) == col(Review.id))
        .where(Review.submission_id == submission_id, Review.id != latest.id)
        .order_by(col(Finding.id).desc())
    ).all()
    seen: set[tuple[str, str, str | None]] = set()
    for f in earlier:
        key = _finding_key(f)
        if key in still_there or key in seen:
            continue
        seen.add(key)
        f.resolved = True
        session.add(f)


# --- POST /api/reviews/{id}/flag -----------------------------------------------


@router.post("/reviews/{review_id}/flag", status_code=201)
def flag_review(review_id: int, body: FlagIn, session: Session = Depends(get_session)) -> FlagOut:
    """The learner disagrees with the AI: the whole review, one finding, or one grade.

    A flag is stored for a person to look at. It never changes a score, reopens a gate or
    touches GitHub, so it can't become a way around the gate. It works after a pass too.
    """
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    if body.finding_id is not None:
        finding = session.get(Finding, body.finding_id)
        if finding is None or finding.review_id != review.id:
            raise HTTPException(status_code=422, detail="That finding isn't part of this review.")

    if body.answer_id is not None:
        # An answer belongs to a question on a gate. It has to be this review's PR's gate.
        answer = session.get(Answer, body.answer_id)
        question = session.get(Question, answer.question_id) if answer else None
        gate = session.get(Gate, question.gate_id) if question else None
        if gate is None or gate.submission_id != review.submission_id:
            raise HTTPException(status_code=422, detail="That answer isn't from this review's pull request.")

    flag = Flag(review_id=review.id, finding_id=body.finding_id, answer_id=body.answer_id, reason=body.reason)  # type: ignore[arg-type]
    session.add(flag)
    session.commit()
    session.refresh(flag)
    # The id only: the reason is the learner's own words and stays out of the logs.
    logger.info("Review %s flagged (flag %s)", review.id, flag.id)
    return FlagOut(id=flag.id, created_at=flag.created_at)  # type: ignore[arg-type]
