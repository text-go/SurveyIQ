from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.services.nlp_engine import run_full_analysis
from app.services.ai_chat import ask_survey_agent
from app.services.reporting import build_report_summary, send_report_to_webhook
from app.models.user import User
from app.models.analysis import SentimentResult, Theme
from app.models.survey import Answer, Question, Survey
from app.schemas.analysis import AgentQueryRequest, AgentQueryResponse, ChatMessage, SentimentResponse, ThemeResponse, ReportDispatchRequest, ReportDispatchResponse
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/nlp", tags=["nlp"])

@router.post("/{survey_id}/analyze")
async def analyze_survey(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await run_full_analysis(db, survey_id)
    return {"message": "Analysis complete"}

@router.get("/{survey_id}/sentiment", response_model=list[SentimentResponse])
async def get_sentiment(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    res = await db.execute(
        select(SentimentResult)
        .join(Answer, Answer.id == SentimentResult.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id)
    )
    return res.scalars().all()

@router.get("/{survey_id}/themes", response_model=list[ThemeResponse])
async def get_themes(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    res = await db.execute(select(Theme).where(Theme.survey_id == survey_id))
    return res.scalars().all()

@router.get("/{survey_id}/summary")
async def get_ai_summary(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    try:
        summary = await build_report_summary(
            db=db,
            survey_id=survey_id,
            user_query="Provide a concise executive summary of the survey, highlight the most important opportunities, and suggest 3 immediate next actions.",
            provider="mistral",
            mode="rapid_summary",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"summary": summary}

@router.post("/{survey_id}/chat", response_model=AgentQueryResponse)
async def chat_with_survey_agent(
    survey_id: int,
    payload: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    try:
        reply = await ask_survey_agent(
            db=db,
            survey_id=survey_id,
            user_query=payload.query,
            provider=payload.provider,
            mode=payload.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AgentQueryResponse(
        messages=[
            ChatMessage(role="assistant", content=reply),
        ]
    )


@router.post("/{survey_id}/report/send", response_model=ReportDispatchResponse)
async def send_survey_report(
    survey_id: int,
    payload: ReportDispatchRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    try:
        report_text = await build_report_summary(
            db=db,
            survey_id=survey_id,
            user_query=payload.query,
            provider=payload.provider,
            mode=payload.mode,
        )
        dispatch_status = await send_report_to_webhook(
            report_body=report_text,
            recipient=payload.recipient,
            webhook_url=payload.webhook_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ReportDispatchResponse(
        status=dispatch_status["status"],
        message=dispatch_status["message"],
        recipient=dispatch_status.get("recipient"),
        report=report_text,
    )
