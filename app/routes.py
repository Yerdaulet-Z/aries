from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import AnalysisStatus
from app.queue.client import MessageQueue
from app.schemas import ArticleResponse
from app.services import articles as article_service
from app.services.news import news_service, RateLimitExceeded

router = APIRouter(prefix="/api/articles", tags=["Articles"])
_mq: MessageQueue | None = None
ANALYSIS_QUEUE = "article_analysis"

def set_message_queue(mq: MessageQueue) -> None:
    global _mq
    _mq = mq

def _get_mq() -> MessageQueue:
    if _mq is None:
        raise RuntimeError("MessageQueue not initialized")
    return _mq

@router.get("/search", response_model=list[ArticleResponse])
async def search_articles(
    q: str = Query(..., description="Query to search on GNews"),
    max_results: int = Query(10, ge=1, le=10),
    lang: str = Query("en", description="Language code (e.g. 'en')"),
    country: Optional[str] = Query(None, description="Country code (e.g. 'us')"),
    sortby: Optional[str] = Query(None, description="'publishedAt' or 'relevance'"),
    from_date: Optional[str] = Query(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')"),
    to_date: Optional[str] = Query(None, description="UTC ISO format date (e.g. '2023-01-01T00:00:00Z')"),
    db: AsyncSession = Depends(get_db),
):
    try:
        raw_articles = await news_service.search(
            query=q,
            max_results=max_results,
            lang=lang,
            country=country,
            sortby=sortby,
            from_date=from_date,
            to_date=to_date,
        )
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
        
    articles = await article_service.upsert_from_gnews(db, raw_articles)
    return articles

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    q: Optional[str] = Query(None, description="Full-text search on DB"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by status"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await article_service.query(
        db, q=q, status=status, start_date=start_date, end_date=end_date, limit=limit, offset=offset
    )

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("/{article_id}/analyze", status_code=202)
async def analyze_article(article_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.analysis_status == AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Article already analyzed")
    if article.analysis_status in (AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING):
        raise HTTPException(status_code=409, detail=f"Article already {article.analysis_status.value}")

    await article_service.update_status(db, article, AnalysisStatus.QUEUED)
    await _get_mq().publish(ANALYSIS_QUEUE, {"article_id": str(article.id)})
    return {"message": "Analysis job queued", "article_id": str(article.id), "status": AnalysisStatus.QUEUED}
