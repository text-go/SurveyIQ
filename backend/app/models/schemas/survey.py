from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.survey import QuestionType

class SurveyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: str = "manual"

class QuestionResponse(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    order_index: int
    options: Optional[List[str]] = None

    class Config:
        from_attributes = True

class AnswerResponse(BaseModel):
    id: int
    question_id: int
    value_numeric: Optional[int] = None
    value_text: Optional[str] = None

    class Config:
        from_attributes = True

class ResponseResponse(BaseModel):
    id: int
    respondent_id: str
    submitted_at: datetime
    answers: List[AnswerResponse] = []

    class Config:
        from_attributes = True

class SurveyResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    status: str
    questions: List[QuestionResponse] = []

    class Config:
        from_attributes = True

class SurveyListResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    status: str

    class Config:
        from_attributes = True

class SurveyUploadResponse(BaseModel):
    survey_id: int
    name: str
    question_count: int
    response_count: int
    message: str

class SurveyStatsResponse(BaseModel):
    total_responses: int
    response_rate: Optional[float] = None
    date_range: Optional[Dict[str, datetime]] = None
    question_count: int
