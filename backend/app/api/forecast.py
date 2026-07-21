from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.services.forecasting import run_forecast
from app.models.user import User
from app.models.analysis import ForecastResult
from app.models.survey import Answer, Survey
from app.schemas.analysis import ForecastResultResponse
from fastapi import HTTPException
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.post("/{survey_id}", response_model=ForecastResultResponse)
async def forecast_survey(survey_id: int, question_id: int, periods: int = 3, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    res = await db.execute(
        select(Answer.value_numeric)
        .where(Answer.question_id == question_id, Answer.value_numeric.isnot(None))
        .order_by(Answer.created_at)
    )
    values = [r[0] for r in res.all()]
    if not values:
        raise HTTPException(status_code=400, detail="Not enough numeric data for forecast")
    
    result = await run_forecast(db, survey_id, question_id, values, periods)
    return result

@router.get("/{survey_id}/results", response_model=list[ForecastResultResponse])
async def get_forecast_results(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    res = await db.execute(select(ForecastResult).where(ForecastResult.survey_id == survey_id))
    return res.scalars().all()

@router.get("/{survey_id}/anomalies")
async def get_anomalies(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(ForecastResult).where(ForecastResult.survey_id == survey_id))
    results = res.scalars().all()
    anomalies = []
    for r in results:
        if r.anomalies:
            anomalies.extend(r.anomalies)
    return anomalies
