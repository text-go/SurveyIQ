from __future__ import annotations

from collections import Counter
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mistralai import ChatMistralAI
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.models.analysis import SentimentResult, Theme
from app.models.survey import Answer, Question, Response, Survey


def get_chat_model(provider: str = "mistral"):
    provider_name = (provider or "mistral").lower()

    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.3,
            google_api_key=settings.GEMINI_API_KEY,
        )

    if not settings.MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not configured")

    return ChatMistralAI(
        model="mistral-large-latest",
        api_key=settings.MISTRAL_API_KEY,
        temperature=0.3,
    )


async def get_survey_research_context(db: AsyncSession, survey_id: int) -> dict[str, Any]:
    survey_result = await db.execute(select(Survey).where(Survey.id == survey_id))
    survey = survey_result.scalars().first()
    if survey is None:
        raise ValueError("Survey not found")

    response_count = await db.scalar(
        select(func.count(Response.id)).where(Response.survey_id == survey_id)
    ) or 0

    question_count = await db.scalar(
        select(func.count(Question.id)).where(Question.survey_id == survey_id)
    ) or 0

    question_rows = await db.execute(
        select(Question.id, Question.text, Question.question_type, Question.options)
        .where(Question.survey_id == survey_id)
        .order_by(Question.order_index)
    )
    questions = question_rows.all()

    answer_rows = await db.execute(
        select(Answer.question_id, Answer.value_numeric, Answer.value_text)
        .where(Answer.question_id.in_([q[0] for q in questions]))
    )
    answer_items = answer_rows.all()

    theme_rows = await db.execute(
        select(Theme.name, Theme.keywords, Theme.response_count, Theme.avg_sentiment)
        .where(Theme.survey_id == survey_id)
        .order_by(Theme.response_count.desc())
    )
    themes = theme_rows.all()

    sentiment_rows = await db.execute(
        select(SentimentResult.label, func.count(SentimentResult.id))
        .join(Answer, Answer.id == SentimentResult.answer_id)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id)
        .group_by(SentimentResult.label)
    )
    sentiment_counts = dict(sentiment_rows.all())

    question_context = []
    answer_lookup: dict[int, list[str]] = {}
    for answer_id, numeric_value, text_value in answer_items:
        question_id = answer_id
        answer_lookup.setdefault(question_id, [])
        if numeric_value is not None:
            answer_lookup[question_id].append(str(numeric_value))
        if text_value:
            answer_lookup[question_id].append(text_value)

    for q_id, text, q_type, options in questions:
        values = answer_lookup.get(q_id, [])
        counts = Counter(values)
        distribution = ", ".join(f"{value} ({count})" for value, count in counts.most_common(6))
        question_context.append({
            "question_id": q_id,
            "question": text,
            "type": q_type.value if q_type else "unknown",
            "options": options or [],
            "distribution": distribution or "No structured responses yet",
        })

    return {
        "survey_name": survey.name,
        "survey_description": survey.description or "No description provided",
        "response_count": response_count,
        "question_count": question_count,
        "sentiment_counts": sentiment_counts,
        "theme_summary": [
            {
                "name": theme[0],
                "keywords": theme[1],
                "response_count": theme[2],
                "avg_sentiment": theme[3],
            }
            for theme in themes
        ],
        "questions": question_context,
    }


async def ask_survey_agent(db: AsyncSession, survey_id: int, user_query: str, provider: str = "mistral", mode: str = "deep_research") -> str:
    context = await get_survey_research_context(db, survey_id)

    mode_prompt = {
        "rapid_summary": "Reply with a concise executive summary, the strongest evidence from the survey, and 3 immediate actions.",
        "deep_research": "Act like a senior market research analyst. Produce a grounded, evidence-led deep research answer with: (1) key findings, (2) evidence from the survey, (3) likely drivers, (4) recommendations, and (5) next-step research ideas.",
        "action_plan": "Turn the survey results into a focused action plan for a leadership team. Emphasize owner, priority, and expected outcome.",
    }.get(mode, "Respond with a practical business-friendly analysis grounded in the survey data.")

    system_prompt = (
        "You are SurveyIQ's research copilot for customer feedback data. "
        "Use only the survey evidence provided below and do not invent numbers. "
        "If any information is missing, say so briefly. "
        f"Mode: {mode_prompt}"
    )

    user_prompt = (
        f"Survey: {context['survey_name']}\n"
        f"Description: {context['survey_description']}\n"
        f"Responses: {context['response_count']}\n"
        f"Questions: {context['question_count']}\n"
        f"Sentiment breakdown: {context['sentiment_counts']}\n"
        f"Themes: {context['theme_summary']}\n"
        f"Question evidence:\n"
        + "\n".join(
            f"- Q{item['question_id']}: {item['question']} [{item['type']}] | Distribution: {item['distribution']}"
            for item in context['questions']
        )
        + f"\n\nUser research request: {user_query}"
    )

    llm = get_chat_model(provider)
    response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    return response.content if hasattr(response, "content") else str(response)
