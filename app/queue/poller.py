"""
Background daemon that polls GNews for top headlines,
saves them directly to PostgreSQL, and respects a configurable daily article limit.

The rate limit is read dynamically from .env on every cycle,
so you can change it without restarting the container.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from dotenv import dotenv_values
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import Article
from app.services.news import news_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _parse_date(date_str: str | None) -> datetime:
    """Parse ISO date string from GNews, fallback to now()."""
    if not date_str:
        return datetime.now(timezone.utc)
    try:
        cleaned = date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str
        return datetime.fromisoformat(cleaned)
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


def _read_rate_limit() -> int:
    """Read GNEWS_RATE_LIMIT dynamically from the mounted .env file."""
    try:
        env = dotenv_values(".env")
        return max(int(env.get("GNEWS_RATE_LIMIT", settings.GNEWS_RATE_LIMIT)), 1)
    except (ValueError, TypeError):
        return max(settings.GNEWS_RATE_LIMIT, 1)


async def _save_articles(raw_articles: list[dict]) -> int:
    """Save raw articles to DB, skip duplicates by URL. Returns count of NEW articles saved."""
    saved = 0
    async with AsyncSessionLocal() as db:
        for item in raw_articles:
            url = item.get("url")
            if not url:
                continue

            exists = await db.scalar(select(Article.id).where(Article.url == url))
            if exists:
                continue

            article = Article(
                title=item.get("title", ""),
                description=item.get("description"),
                content=item.get("content"),
                url=url,
                image_url=item.get("image"),
                source_name=item.get("source", {}).get("name", "Unknown"),
                published_at=_parse_date(item.get("publishedAt")),
            )
            db.add(article)
            saved += 1

        await db.commit()
    return saved


async def run_poller() -> None:
    """Main poller loop."""
    await init_db()

    articles_today = 0
    reset_date = datetime.now(timezone.utc).date()

    while True:
        try:
            # Reset counter at midnight UTC
            today = datetime.now(timezone.utc).date()
            if today > reset_date:
                articles_today = 0
                reset_date = today

            rate_limit = _read_rate_limit()

            # Check if daily limit is reached
            if articles_today >= rate_limit:
                now = datetime.now(timezone.utc)
                midnight = datetime(
                    now.year, now.month, now.day, tzinfo=timezone.utc
                ) + timedelta(days=1)
                sleep_secs = (midnight - now).total_seconds() + 60
                logger.warning(
                    "Daily limit (%d articles) reached. Sleeping %.1f hours until UTC midnight.",
                    rate_limit, sleep_secs / 3600,
                )
                await asyncio.sleep(sleep_secs)
                continue

            # Fetch articles (capped at remaining quota and GNews max of 10)
            batch_size = min(rate_limit - articles_today, 10)
            logger.info(
                "Polling GNews (batch=%d, today=%d/%d)...",
                batch_size, articles_today, rate_limit,
            )

            raw_articles = await news_service.top_headlines(max_results=batch_size)
            saved = await _save_articles(raw_articles)
            articles_today += len(raw_articles)

            logger.info(
                "Saved %d new articles (%d duplicates). Total today: %d/%d",
                saved, len(raw_articles) - saved, articles_today, rate_limit,
            )

            # Spread fetches evenly across 24h based on how many batches are needed
            total_batches = max((rate_limit + 9) // 10, 1)
            sleep_interval = max(86400 / total_batches, 60)
            logger.info("Sleeping %.0f seconds until next poll...", sleep_interval)
            await asyncio.sleep(sleep_interval)

        except Exception as e:
            logger.error("Poller error: %s", e)
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(run_poller())
