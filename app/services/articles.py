from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AnalysisStatus, Article, AISummary, Sentiment

logger = logging.getLogger(__name__)

def _parse_date(date_str: str | None) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        cleaned = date_str.replace("Z", "+00:00") if date_str.endswith("Z") else date_str
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).replace(tzinfo=None)

async def upsert_from_gnews(db: AsyncSession, raw_articles: list[dict]) -> list[Article]:
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
            "published_at": _parse_date(item.get("publishedAt")),
            "analysis_status": AnalysisStatus.PENDING,
        })

    if rows:
        stmt = pg_insert(Article).values(rows).on_conflict_do_nothing(index_elements=["url"])
        await db.execute(stmt)
        await db.commit()

    result = await db.execute(
        select(Article)
        .options(joinedload(Article.ai_summary))
        .where(Article.url.in_(urls))
        .order_by(Article.published_at.desc())
    )
    return list(result.scalars().all())

async def get_by_id(db: AsyncSession, article_id: uuid.UUID) -> Optional[Article]:
    result = await db.execute(
        select(Article).options(joinedload(Article.ai_summary)).where(Article.id == article_id)
    )
    return result.scalars().first()

async def query(
    db: AsyncSession,
    *,
    q: Optional[str] = None,
    status: Optional[AnalysisStatus] = None,
    sentiment: Optional[Sentiment] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    sort_by: str = "default",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Article]:
    stmt = select(Article).options(joinedload(Article.ai_summary)).outerjoin(AISummary)
    if q:
        stmt = stmt.where(
            text("to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')) @@ plainto_tsquery('english', :q)")
            .bindparams(q=q)
        )
    if status:
        stmt = stmt.where(Article.analysis_status == status)
    if sentiment:
        stmt = stmt.where(AISummary.sentiment == sentiment)
    if min_score is not None:
        stmt = stmt.where(AISummary.sentiment_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(AISummary.sentiment_score <= max_score)
    if start_date:
        stmt = stmt.where(Article.published_at >= start_date)
    if end_date:
        stmt = stmt.where(Article.published_at <= end_date)
        
    if sort_by == "date_desc":
        stmt = stmt.order_by(Article.published_at.desc())
    elif sort_by == "date_asc":
        stmt = stmt.order_by(Article.published_at.asc())
    elif sort_by == "score_desc":
        stmt = stmt.order_by(AISummary.sentiment_score.desc().nulls_last())
    elif sort_by == "score_asc":
        stmt = stmt.order_by(AISummary.sentiment_score.asc().nulls_last())
    else:
        # Default: COMPLETED first, then date desc
        stmt = stmt.order_by((Article.analysis_status == AnalysisStatus.COMPLETED).desc(), Article.published_at.desc())

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def update_status(db: AsyncSession, article: Article, status: AnalysisStatus) -> None:
    article.analysis_status = status
    await db.commit()
