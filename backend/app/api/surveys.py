from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.database import get_db
from app.models.user import User
from app.models.survey import Survey, Question, Response
from app.schemas.survey import SurveyResponse, SurveyListResponse, SurveyUploadResponse, ResponseResponse
from app.services.auth import get_current_user
from app.services.ingestion import parse_csv, parse_excel, create_survey_from_dataframe

router = APIRouter(prefix="/api/surveys", tags=["surveys"])

@router.get("", response_model=list[SurveyListResponse])
async def list_surveys(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Survey).where(Survey.user_id == user.id))
    return res.scalars().all()

@router.post("/upload", response_model=SurveyUploadResponse)
async def upload_survey(file: UploadFile = File(...), db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    contents = await file.read()
    if file.filename.endswith(".csv"):
        df = parse_csv(contents)
    elif file.filename.endswith(".xlsx"):
        df = parse_excel(contents)
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    survey = await create_survey_from_dataframe(db, df, file.filename, user.id)
    
    q_res = await db.execute(select(Question).where(Question.survey_id == survey.id))
    r_res = await db.execute(select(Response).where(Response.survey_id == survey.id))
    
    return {
        "survey_id": survey.id,
        "name": survey.name,
        "question_count": len(q_res.scalars().all()),
        "response_count": len(r_res.scalars().all()),
        "message": "Upload successful"
    }

@router.get("/{survey_id}", response_model=SurveyResponse)
async def get_survey(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    q_res = await db.execute(select(Question).where(Question.survey_id == survey.id))
    survey.questions = q_res.scalars().all()
    return survey

@router.delete("/{survey_id}")
async def delete_survey(survey_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    
    await db.delete(survey)
    await db.commit()
    return {"message": "Deleted"}

@router.get("/{survey_id}/responses", response_model=list[ResponseResponse])
async def get_responses(survey_id: int, skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    survey_res = await db.execute(select(Survey).where(Survey.id == survey_id, Survey.user_id == user.id))
    survey = survey_res.scalars().first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    res = await db.execute(select(Response).where(Response.survey_id == survey_id).offset(skip).limit(limit))
    return res.scalars().all()
