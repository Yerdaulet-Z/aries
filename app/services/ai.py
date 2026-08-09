from __future__ import annotations
import logging
from openai import AsyncOpenAI
from app.core.config import settings
from app.db.models import Sentiment
from app.schemas.articles import AnalysisResult

logger = logging.getLogger(__name__)

MODEL = "gpt-4.1-nano"
SYSTEM_PROMPT = """You are an expert news analyst and financial researcher. Your task is to extract deep insights from news articles.
Given the title and content of an article, you must provide:
1. A highly coherent, concise, and factual summary of the core narrative. Exclude any journalistic fluff and focus strictly on the key events, entities, and implications.
2. The overall sentiment of the article (POSITIVE, NEUTRAL, or NEGATIVE) based on its tone and factual reporting.
3. A granular sentiment score ranging from -1.0 (extremely negative/bearish) to 1.0 (extremely positive/bullish), where 0.0 represents a strictly objective or neutral tone.

Return the result strictly conforming to the requested schema."""

class AIService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def analyze(self, title: str, text: str) -> tuple[AnalysisResult, dict]:
        user_content = f"Title: {title}\n\nContent: {text}"
        completion = await self._client.beta.chat.completions.parse(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format=AnalysisResult,
        )

        result = completion.choices[0].message.parsed
        if not result:
            raise ValueError("OpenAI failed to return parsed structured output.")

        raw_response = completion.model_dump(mode="json")
        logger.info("AI analysis complete: sentiment=%s score=%.2f", result.sentiment, result.sentiment_score)
        return result, raw_response

ai_service = AIService()
