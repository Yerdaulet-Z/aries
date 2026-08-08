from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalysisStatus, Article
from app.schemas import AnalysisResult

logger = logging.getLogger(__name__)


async def upsert_from_gnews(db: AsyncSession, raw_articles: list[dict]) -> list[Article]:
    """
    Bulk upsert articles from GNews API response into PostgreSQL.

    Uses INSERT ... ON CONFLICT (url) DO NOTHING to prevent duplicates.
    Returns all matching articles (both newly inserted and pre-existing).
    """
    if not raw_articles:
        return []

    rows = []
    urls = []
    seen_urls = set()
    for item in raw_articles:
        url = item.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        urls.append(url)
        rows.append({
            "title": item.get("title", ""),
            "description": item.get("description"),
            "content": item.get("content"),
            "url": url,
            "image_url": item.get("image"),
            "source_name": item.get("source", {}).get("name", "Unknown"),
            "published_at": item.get("publishedAt"),
        })

    if rows:
        stmt = pg_insert(Article).values(rows).on_conflict_do_nothing(index_elements=["url"])
        await db.execute(stmt)
        await db.commit()

    # Return all articles matching the searched URLs (includes pre-existing)
    result = await db.execute(
        select(Article).where(Article.url.in_(urls)).order_by(Article.published_at.desc())
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, article_id: int) -> Optional[Article]:
    """Fetch a single article by primary key."""
    return await db.get(Article, article_id)


async def query(
    db: AsyncSession,
    *,
    q: Optional[str] = None,
    status: Optional[AnalysisStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Article]:
    """
    Query stored articles with optional filters:
    - q: Full-text search on title + description (uses GIN index)
    - status: Filter by analysis status
    - start_date / end_date: Filter by published_at range
    """
    stmt = select(Article)

    # Full-text search using PostgreSQL tsvector (leverages GIN index)
    if q:
        stmt = stmt.where(
            text(
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')) "
                "@@ plainto_tsquery('english', :q)"
            ).bindparams(q=q)
        )

    if status:
        stmt = stmt.where(Article.analysis_status == status)

    if start_date:
        stmt = stmt.where(Article.published_at >= start_date)

    if end_date:
        stmt = stmt.where(Article.published_at <= end_date)

    stmt = stmt.order_by(Article.published_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_status(
    db: AsyncSession, article: Article, status: AnalysisStatus
) -> None:
    """Update article analysis status."""
    article.analysis_status = status
    await db.commit()


async def save_analysis(
    db: AsyncSession, article: Article, result: AnalysisResult
) -> None:
    """Write AI analysis results and mark as COMPLETED."""
    article.summary = result.summary
    article.sentiment = result.sentiment
    article.sentiment_score = result.sentiment_score
    article.analysis_status = AnalysisStatus.COMPLETED
    await db.commit()
    logger.info("Analysis saved for article %d", article.id)


async def mark_failed(db: AsyncSession, article: Article, error: str) -> None:
    """Mark article analysis as FAILED with error message."""
    article.analysis_status = AnalysisStatus.FAILED
    article.analysis_error = error
    await db.commit()
    logger.warning("Analysis failed for article %d: %s", article.id, error)
