import pandas as pd
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.survey import Survey, Question, Response, Answer, QuestionType
import json
import io

def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(file_bytes))

def parse_excel(file_bytes: bytes) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes))

def infer_question_type(series: pd.Series) -> QuestionType:
    series = series.dropna()
    if len(series) == 0:
        return QuestionType.open_text
        
    if pd.api.types.is_numeric_dtype(series):
        unique_vals = series.unique()
        if set(unique_vals).issubset({0, 1}):
            return QuestionType.binary
        if len(unique_vals) <= 7 and series.min() >= 1 and series.max() <= 7:
            return QuestionType.likert
        if series.min() >= 0 and series.max() <= 10:
            return QuestionType.nps
        return QuestionType.multiple_choice
        
    elif pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        str_series = series.astype(str).str.strip().str.lower()
        if set(str_series.unique()).issubset({"yes", "no", "true", "false", "1", "0", "y", "n"}):
            return QuestionType.binary
        avg_len = series.astype(str).str.len().mean()
        if avg_len > 20:
            return QuestionType.open_text
        if len(series.unique()) < len(series) * 0.5:
            return QuestionType.multiple_choice
            
    return QuestionType.open_text

async def create_survey_from_dataframe(db: AsyncSession, df: pd.DataFrame, name: str, user_id: int):
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].str.strip()
    df = df.replace({np.nan: None})

    survey = Survey(name=name, user_id=user_id, source_type="upload")
    db.add(survey)
    await db.flush()

    questions = []
    question_map = {}
    for i, col in enumerate(df.columns):
        if col.lower() in ['respondent_id', 'date', 'id']:
            continue
        q_type = infer_question_type(df[col])
        q = Question(
            survey_id=survey.id,
            text=col,
            question_type=q_type,
            order_index=i
        )
        if q_type in [QuestionType.multiple_choice, QuestionType.binary]:
            q.options = list(df[col].dropna().unique().tolist())
        db.add(q)
        questions.append(q)
        await db.flush()
        question_map[col] = q

    for index, row in df.iterrows():
        resp = Response(
            survey_id=survey.id,
            respondent_id=str(row.get('respondent_id', index))
        )
        db.add(resp)
        await db.flush()

        for col, q in question_map.items():
            val = row[col]
            if val is not None:
                val_num = None
                val_text = None
                if q.question_type in [QuestionType.likert, QuestionType.nps]:
                    try:
                        val_num = int(float(val))
                    except:
                        val_text = str(val)
                else:
                    val_text = str(val)
                
                ans = Answer(
                    response_id=resp.id,
                    question_id=q.id,
                    value_numeric=val_num,
                    value_text=val_text
                )
                db.add(ans)
    
    await db.commit()
    return survey
