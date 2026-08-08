from __future__ import annotations
import logging

from openai import AsyncOpenAI

from app.config import settings
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)

MODEL = "gpt-4.1-nano"

SYSTEM_PROMPT = """You are a news analysis assistant. Given a news article's title and content, produce a structured response capturing the key facts, sentiment, and sentiment score."""

class AIService:
    """OpenAI client for article analysis using structured JSON output."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def analyze(self, title: str, text: str) -> AnalysisResult:
        """
        Send article title + text to OpenAI and parse structured output.

        Returns an AnalysisResult with summary, sentiment, and score.
        Raises on API errors or malformed responses.
        """
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

        logger.info(
            "AI analysis complete: sentiment=%s score=%.2f",
            result.sentiment, result.sentiment_score,
        )
        return result

# Module-level singleton
ai_service = AIService()
