from __future__ import annotations
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class RateLimitExceeded(Exception):
    pass

class NewsService:
    # TODO: Reuse a single httpx.AsyncClient instance instead of creating one per request.
    #       Creating a new client per call wastes TCP connections and skips HTTP/2 multiplexing.
    #       Initialize self._client in __init__ and close it in an explicit shutdown method.
    SEARCH_URL = "https://gnews.io/api/v4/search"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        lang: str = "en",
        country: str | None = None,
        sortby: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> list[dict]:
        params = {
            "q": query,
            "lang": lang,
            "max": min(max_results, 10),
            "apikey": settings.GNEWS_API_KEY,
        }
        if country:
            params["country"] = country
        if sortby:
            params["sortby"] = sortby
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.SEARCH_URL,
                params=params,
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
