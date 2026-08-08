"""
RabbitMQ worker for AI analysis of articles.

Consumes from 'article_analysis' queue, calls OpenAI for summary + sentiment,
and writes results back to PostgreSQL.

Processing speed is throttled by WORKER_SLEEP_SECONDS (configurable via .env).

Run as a standalone process:
    python -m app.queue.consumer
"""
from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import AnalysisStatus, Article
from app.queue.client import MessageQueue
from app.services.ai import ai_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

QUEUE_NAME = "article_analysis"


async def process_analysis(payload: dict) -> None:
    """
    Worker callback: processes a single article analysis job.

    State transitions: QUEUED -> PROCESSING -> COMPLETED / FAILED
    """
    article_id = payload.get("article_id")
    if not article_id:
        logger.error("Received message without article_id: %s", payload)
        return

    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            logger.warning("Article %s not found, skipping", article_id)
            return

        if article.analysis_status == AnalysisStatus.COMPLETED:
            logger.info("Article %d already analyzed, skipping", article.id)
            return

        # Transition to PROCESSING
        article.analysis_status = AnalysisStatus.PROCESSING
        await db.commit()
        logger.info("Processing article %d: %s", article.id, article.title[:60])

        try:
            text = "\n".join(
                part for part in [article.description or "", article.content or ""] if part
            )
            result = await ai_service.analyze(title=article.title, text=text)

            # SUCCESS
            article.summary = result.summary
            article.sentiment = result.sentiment
            article.sentiment_score = result.sentiment_score
            article.analysis_status = AnalysisStatus.COMPLETED
            await db.commit()
            logger.info(
                "Article %d analyzed: sentiment=%s score=%.2f",
                article.id, result.sentiment, result.sentiment_score,
            )

        except Exception as err:
            # FAILURE
            article.analysis_status = AnalysisStatus.FAILED
            article.analysis_error = str(err)
            await db.commit()
            logger.exception("Analysis failed for article %d", article.id)

    # Throttle: configurable sleep between jobs
    logger.info("Sleeping %ds before next job...", settings.WORKER_SLEEP_SECONDS)
    await asyncio.sleep(settings.WORKER_SLEEP_SECONDS)


async def main() -> None:
    """Start the analysis worker."""
    await init_db()
    logger.info(
        "Starting analysis worker (sleep=%ds between jobs)...",
        settings.WORKER_SLEEP_SECONDS,
    )

    mq = MessageQueue(settings.RABBITMQ_URL)
    await mq.connect()

    try:
        await mq.consume(QUEUE_NAME, process_analysis)
    finally:
        await mq.close()


if __name__ == "__main__":
    asyncio.run(main())
