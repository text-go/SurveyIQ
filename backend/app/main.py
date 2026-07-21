from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import create_tables

from app.api import auth, surveys, analytics, nlp, forecast

app = FastAPI(
    title="SurveyIQ API",
    description="AI-Powered Survey & Feedback Intelligence Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    await create_tables()

app.include_router(auth.router)
app.include_router(surveys.router)
app.include_router(analytics.router)
app.include_router(nlp.router)
app.include_router(forecast.router)

@app.get("/")
async def root():
    return {"message": "Welcome to SurveyIQ API"}
