from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.survey import Survey, Question, Response, Answer, QuestionType
import pandas as pd
import numpy as np

async def get_descriptive_stats(db: AsyncSession, survey_id: int):
    result = await db.execute(
        select(Question.id, Answer.value_numeric)
        .join(Answer, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id, Answer.value_numeric.isnot(None))
    )
    data = result.all()
    if not data:
        return {}
    df = pd.DataFrame(data, columns=["q_id", "val"])
    stats = {}
    for q_id, group in df.groupby("q_id"):
        stats[int(q_id)] = {
            "mean": float(group["val"].mean()),
            "median": float(group["val"].median()),
            "std": float(group["val"].std()) if len(group) > 1 else 0.0,
            "min": float(group["val"].min()),
            "max": float(group["val"].max())
        }
    return stats

async def get_response_distribution(db: AsyncSession, survey_id: int, question_id: int):
    q = await db.get(Question, question_id)
    if not q:
        return {}
    result = await db.execute(
        select(Answer.value_numeric, Answer.value_text, func.count(Answer.id))
        .where(Answer.question_id == question_id)
        .group_by(Answer.value_numeric, Answer.value_text)
    )
    dist = {}
    for num, txt, count in result:
        key = str(num) if num is not None else str(txt)
        dist[key] = count
    return dist

async def calculate_nps(db: AsyncSession, survey_id: int):
    result = await db.execute(
        select(Answer.value_numeric)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id, Question.question_type == QuestionType.nps, Answer.value_numeric.isnot(None))
    )
    scores = [r[0] for r in result.all()]
    if not scores:
        return {"nps": 0, "promoters": 0, "passives": 0, "detractors": 0}
    promoters = sum(1 for s in scores if s >= 9)
    passives = sum(1 for s in scores if s in [7, 8])
    detractors = sum(1 for s in scores if s <= 6)
    total = len(scores)
    return {
        "nps": ((promoters - detractors) / total) * 100,
        "promoters": promoters,
        "passives": passives,
        "detractors": detractors,
        "promoter_pct": (promoters / total) * 100,
        "passive_pct": (passives / total) * 100,
        "detractor_pct": (detractors / total) * 100
    }

async def get_cross_tabulation(db: AsyncSession, survey_id: int, q1_id: int, q2_id: int):
    res = await db.execute(
        select(Answer.response_id, Answer.question_id, Answer.value_numeric, Answer.value_text)
        .where(Answer.question_id.in_([q1_id, q2_id]))
    )
    data = res.all()
    if not data:
        return {}
    df = pd.DataFrame(data, columns=["resp_id", "q_id", "val_num", "val_txt"])
    df['val'] = df['val_num'].combine_first(df['val_txt'])
    pivoted = df.pivot(index='resp_id', columns='q_id', values='val').dropna()
    if pivoted.empty:
        return {}
    crosstab = pd.crosstab(pivoted[q1_id], pivoted[q2_id])
    return crosstab.to_dict()

async def get_survey_summary(db: AsyncSession, survey_id: int):
    resp_count = await db.scalar(select(func.count(Response.id)).where(Response.survey_id == survey_id))
    q_count = await db.scalar(select(func.count(Question.id)).where(Question.survey_id == survey_id))
    dates = await db.execute(
        select(func.min(Response.submitted_at), func.max(Response.submitted_at)).where(Response.survey_id == survey_id)
    )
    min_d, max_d = dates.first()
    return {
        "total_responses": resp_count or 0,
        "question_count": q_count or 0,
        "date_range": {"start": min_d, "end": max_d} if min_d else None
    }
