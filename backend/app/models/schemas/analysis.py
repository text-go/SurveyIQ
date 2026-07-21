from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class SentimentResponse(BaseModel):
    id: int
    answer_id: int
    score: float
    label: str
    confidence: float

    class Config:
        from_attributes = True

class ThemeResponse(BaseModel):
    id: int
    name: str
    keywords: List[str]
    response_count: int
    avg_sentiment: float

    class Config:
        from_attributes = True

class ThemeListResponse(BaseModel):
    themes: List[ThemeResponse]

class ForecastRequest(BaseModel):
    periods: int = 3

class ForecastResponse(BaseModel):
    metric_name: str
    historical_values: List[float]
    predicted_values: List[float]
    confidence_intervals: List[List[float]]
    anomalies: Optional[List[Dict[str, Any]]] = []

class ForecastResultResponse(ForecastResponse):
    id: int
    survey_id: int
    question_id: int
    created_at: Optional[datetime]

    class Config:
        from_attributes = True

class AnomalyResponse(BaseModel):
    anomalies: List[Dict[str, Any]]

class AgentQueryRequest(BaseModel):
    query: str
    survey_id: int
    provider: str = "mistral"
    mode: str = "deep_research"

class ChatMessage(BaseModel):
    role: str
    content: str

class AgentQueryResponse(BaseModel):
    messages: List[ChatMessage]

class ReportDispatchRequest(BaseModel):
    query: str
    provider: str = "mistral"
    mode: str = "deep_research"
    recipient: Optional[str] = None
    webhook_url: Optional[str] = None

class ReportDispatchResponse(BaseModel):
    status: str
    message: str
    recipient: Optional[str] = None
    report: Optional[str] = None
