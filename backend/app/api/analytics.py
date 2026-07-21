from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.survey import Survey
from app.services.statistics import get_descriptive_stats, get_response_distribution, calculate_nps, get_cross_tabulation, get_survey_summary
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

async def require_survey_owner(db: AsyncSession, survey_id: int, user: User):
    res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return survey

@router.get("/{survey_id}/stats")
async def get_stats(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await require_survey_owner(db, survey_id, user)
    return await get_descriptive_stats(db, survey_id)

@router.get("/{survey_id}/distribution/{question_id}")
async def get_distribution(survey_id: int, question_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await require_survey_owner(db, survey_id, user)
    return await get_response_distribution(db, survey_id, question_id)

@router.get("/{survey_id}/nps")
async def get_nps(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await require_survey_owner(db, survey_id, user)
    return await calculate_nps(db, survey_id)

@router.post("/{survey_id}/crosstab")
async def get_crosstab(survey_id: int, q1_id: int, q2_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await require_survey_owner(db, survey_id, user)
    return await get_cross_tabulation(db, survey_id, q1_id, q2_id)

@router.get("/{survey_id}/summary")
async def get_summary(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    await require_survey_owner(db, survey_id, user)
    return await get_survey_summary(db, survey_id)
