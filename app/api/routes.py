from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import AnalysisStatus
from app.core.rabbitmq import MessageQueue
from app.core.schemas import ArticleResponse, SearchArticlesQuery, ListArticlesQuery
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
    query_params: SearchArticlesQuery = Depends(),
    db: AsyncSession = Depends(get_db),
):
    try:
        raw_articles = await news_service.search(
            query=query_params.q,
            max_results=query_params.max_results,
            lang=query_params.lang,
            country=query_params.country,
            sortby=query_params.sortby,
            from_date=query_params.from_date,
            to_date=query_params.to_date,
        )
    except RateLimitExceeded as e:
        raise HTTPException(status_code=429, detail=str(e))
        
    articles = await article_service.upsert_from_gnews(db, raw_articles)
    return articles

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    query_params: ListArticlesQuery = Depends(),
    db: AsyncSession = Depends(get_db),
):
    sort_val = query_params.sort_by.value if hasattr(query_params.sort_by, "value") else str(query_params.sort_by)
    return await article_service.query(
        db,
        q=query_params.q,
        status=query_params.status,
        sentiment=query_params.sentiment,
        min_score=query_params.min_score,
        max_score=query_params.max_score,
        sort_by=sort_val,
        start_date=query_params.start_date,
        end_date=query_params.end_date,
        limit=query_params.limit,
        offset=query_params.offset,
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
    if article.analysis_status in (
        AnalysisStatus.QUEUED,
        AnalysisStatus.PROCESSING,
        AnalysisStatus.EXTRACTING_TEXT,
        AnalysisStatus.GENERATING_SUMMARY,
        AnalysisStatus.SAVING_RESULTS,
    ):
        raise HTTPException(status_code=409, detail=f"Article analysis already in progress ({article.analysis_status.value})")

    await article_service.update_status(db, article, AnalysisStatus.QUEUED)
    await _get_mq().publish(ANALYSIS_QUEUE, {"article_id": str(article.id)})
    return {"message": "Analysis job queued", "article_id": str(article.id), "status": AnalysisStatus.QUEUED}
