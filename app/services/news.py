from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class NewsService:
    """GNews API client for fetching news articles."""

    HEADLINES_URL = "https://gnews.io/api/v4/top-headlines"
    SEARCH_URL = "https://gnews.io/api/v4/search"

    async def top_headlines(self, max_results: int = 10) -> list[dict]:
        """Fetch top headlines. max_results capped at 10 (GNews free tier)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.HEADLINES_URL,
                params={
                    "lang": "en",
                    "max": min(max_results, 10),
                    "apikey": settings.GNEWS_API_KEY,
                },
            )
            response.raise_for_status()

        articles = response.json().get("articles", [])
        logger.info("GNews top-headlines returned %d articles", len(articles))
        return articles

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        """Search GNews for articles matching the query."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.SEARCH_URL,
                params={
                    "q": query,
                    "lang": "en",
                    "max": min(max_results, 10),
                    "apikey": settings.GNEWS_API_KEY,
                },
            )
            response.raise_for_status()

        articles = response.json().get("articles", [])
        logger.info("GNews search: query=%r returned %d articles", query, len(articles))
        return articles


news_service = NewsService()
