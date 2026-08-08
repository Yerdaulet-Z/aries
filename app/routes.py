"""
All REST API endpoints — single file, single Swagger UI at /docs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AnalysisStatus
from app.queue.client import MessageQueue
from app.schemas import ArticleResponse
from app.services import articles as article_service

router = APIRouter(prefix="/api/articles", tags=["Articles"])

# RabbitMQ client — set during app lifespan via set_message_queue()
_mq: MessageQueue | None = None

ANALYSIS_QUEUE = "article_analysis"


def set_message_queue(mq: MessageQueue) -> None:
    """Called from main.py lifespan to inject the shared MQ connection."""
    global _mq
    _mq = mq


def _get_mq() -> MessageQueue:
    if _mq is None:
        raise RuntimeError("MessageQueue not initialized")
    return _mq


# --------------------------------------------------------------------------- #
# 1. List — query stored articles with filters
# --------------------------------------------------------------------------- #

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    q: Optional[str] = Query(None, description="Full-text search on title + description"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by analysis status"),
    start_date: Optional[datetime] = Query(None, description="Filter: published_at >= start_date"),
    end_date: Optional[datetime] = Query(None, description="Filter: published_at <= end_date"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Query all stored articles with optional filters.

    Supports full-text search (GIN index), date range filtering,
    and analysis status filtering. Results ordered by published_at DESC.
    """
    return await article_service.query(
        db,
        q=q,
        status=status,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------------- #
# 2. Detail — single article with analysis results
# --------------------------------------------------------------------------- #

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch a single article by ID, including its AI analysis results.
    """
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


# --------------------------------------------------------------------------- #
# 3. Analyze — trigger AI analysis for a single article
# --------------------------------------------------------------------------- #

@router.post("/{article_id}/analyze", status_code=202)
async def analyze_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger AI analysis (summary + sentiment) for a specific article.

    Publishes a job to RabbitMQ and returns 202 Accepted immediately.
    Poll GET /{id} for results.
    """
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if article.analysis_status == AnalysisStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Article already analyzed")

    if article.analysis_status in (AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING):
        raise HTTPException(
            status_code=409,
            detail=f"Article analysis already {article.analysis_status.value}",
        )

    # Set QUEUED and publish to RabbitMQ
    await article_service.update_status(db, article, AnalysisStatus.QUEUED)
    await _get_mq().publish(ANALYSIS_QUEUE, {"article_id": article.id})

    return {
        "message": "Analysis job queued",
        "article_id": article.id,
        "status": AnalysisStatus.QUEUED,
    }
