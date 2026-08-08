from __future__ import annotations
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class RateLimitExceeded(Exception):
    pass

class NewsService:
    SEARCH_URL = "https://gnews.io/api/v4/search"

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.SEARCH_URL,
                params={"q": query, "lang": "en", "max": min(max_results, 10), "apikey": settings.GNEWS_API_KEY}
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("GNews API returned 429 Too Many Requests.")
                    raise RateLimitExceeded("GNews API rate limit exceeded (429).") from e
                raise e

        return response.json().get("articles", [])

news_service = NewsService()
