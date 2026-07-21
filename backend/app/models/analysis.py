from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.database import Base

class SentimentResult(Base):
    __tablename__ = "sentiment_results"
    id = Column(Integer, primary_key=True, index=True)
    answer_id = Column(Integer, ForeignKey("answers.id"))
    score = Column(Float)
    label = Column(String)
    confidence = Column(Float)
    model_used = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Theme(Base):
    __tablename__ = "themes"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    name = Column(String)
    keywords = Column(JSON)
    response_count = Column(Integer)
    avg_sentiment = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ThemeAssignment(Base):
    __tablename__ = "theme_assignments"
    id = Column(Integer, primary_key=True, index=True)
    theme_id = Column(Integer, ForeignKey("themes.id"))
    answer_id = Column(Integer, ForeignKey("answers.id"))
    confidence = Column(Float)

class ForecastResult(Base):
    __tablename__ = "forecast_results"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    metric_name = Column(String)
    historical_values = Column(JSON)
    predicted_values = Column(JSON)
    confidence_intervals = Column(JSON)
    anomalies = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
