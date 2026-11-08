"""Neel's comprehension gate endpoints: /api/gates/{id}.

A gate belongs to one PR. It always shows the latest push: that push's review, findings
and questions. Earlier pushes' questions and answers stay in the DB as history.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Answer, Finding, Gate, Question, Review, Submission, Ticket
from app.schemas import AnswerOut, FindingOut, GateOut, GateReviewOut, QuestionOut

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
