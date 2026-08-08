from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
import httpx
from dotenv import dotenv_values
from app.config import settings

logger = logging.getLogger(__name__)

class RateLimitExceeded(Exception):
    pass

class NewsService:
    SEARCH_URL = "https://gnews.io/api/v4/search"

    def __init__(self) -> None:
        self._articles_fetched_today: int = 0
        self._reset_date = datetime.now(timezone.utc).date()
        self._cooldown_until: datetime | None = None

    def _get_rate_limit(self) -> int:
        try:
            env = dotenv_values(".env")
            return max(int(env.get("GNEWS_RATE_LIMIT", settings.GNEWS_RATE_LIMIT)), 1)
        except (ValueError, TypeError):
            return max(settings.GNEWS_RATE_LIMIT, 1)

    def _check_rate_limit(self) -> None:
        now = datetime.now(timezone.utc)
        if self._cooldown_until and now < self._cooldown_until:
            raise RateLimitExceeded(f"API is in cooldown until {self._cooldown_until.isoformat()}")
            
        today = now.date()
        if today > self._reset_date:
            self._articles_fetched_today = 0
            self._reset_date = today
            self._cooldown_until = None

        rate_limit = self._get_rate_limit()
        if self._articles_fetched_today >= rate_limit:
            raise RateLimitExceeded(f"Daily limit of {rate_limit} articles reached. Try tomorrow.")

    def _trigger_cooldown(self) -> None:
        now = datetime.now(timezone.utc)
        tomorrow = now.date() + timedelta(days=1)
        self._cooldown_until = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc)
        logger.warning("GNews API returned 429. Cooldown triggered until %s", self._cooldown_until)

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        self._check_rate_limit()
        limit = self._get_rate_limit()
        allowed_count = min(max_results, limit - self._articles_fetched_today)
        if allowed_count <= 0:
            raise RateLimitExceeded(f"Daily limit reached.")
            
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.SEARCH_URL,
                params={"q": query, "lang": "en", "max": min(allowed_count, 10), "apikey": settings.GNEWS_API_KEY}
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    self._trigger_cooldown()
                    raise RateLimitExceeded("GNews rate limit exceeded (429). Cooldown initiated.") from e
                raise e

        articles = response.json().get("articles", [])
        self._articles_fetched_today += len(articles)
        return articles

news_service = NewsService()
