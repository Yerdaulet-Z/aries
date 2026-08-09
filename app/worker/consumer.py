from __future__ import annotations
import asyncio
import logging
import uuid
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import AnalysisStatus, Article, AISummary
from app.core.rabbitmq import MessageQueue
from app.services.ai import ai_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
QUEUE_NAME = "article_analysis"

# TODO: Replace raw asyncio consumer loop with Celery or Temporal for production-grade
#       retry policies, dead-letter queues (DLQ), and exponential backoff.
async def process_analysis(payload: dict) -> None:
    article_id_str = payload.get("article_id")
    if not article_id_str:
        return
    try:
        article_id = uuid.UUID(article_id_str)
    except ValueError:
        return

    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article or article.analysis_status == AnalysisStatus.COMPLETED:
            return

        # Stage 1: Extracting text
        article.analysis_status = AnalysisStatus.EXTRACTING_TEXT
        await db.commit()
        logger.info("Article %s: Extracting content...", article.id)
        # TODO: Remove artificial sleep — exists only for demo progress bar visibility.
        #       In production, the actual HTTP download / text extraction takes real time.
        await asyncio.sleep(max(settings.WORKER_SLEEP_SECONDS, 1.5))

        try:
            text = "\n".join(part for part in [article.description or "", article.content or ""] if part)
            
            # Stage 2: Generating summary via OpenAI
            article.analysis_status = AnalysisStatus.GENERATING_SUMMARY
            await db.commit()
            logger.info("Article %s: Generating AI summary...", article.id)
            await asyncio.sleep(max(settings.WORKER_SLEEP_SECONDS, 1.5))

            result, raw_response = await ai_service.analyze(title=article.title, text=text)

            # Stage 3: Saving results
            article.analysis_status = AnalysisStatus.SAVING_RESULTS
            await db.commit()
            logger.info("Article %s: Saving results...", article.id)
            await asyncio.sleep(max(settings.WORKER_SLEEP_SECONDS, 1.5))

            article.ai_summary = AISummary(
                summary=result.summary,
                sentiment=result.sentiment,
                sentiment_score=result.sentiment_score,
                ai_raw_response=raw_response
            )
            
            # Stage 4: Completed
            article.analysis_status = AnalysisStatus.COMPLETED
            await db.commit()
            logger.info("Article %s analysis complete!", article.id)

        except Exception as err:
            # TODO: Storing error as AISummary row is a workaround. In production,
            #       add an `last_error` column on Article or use a separate `task_runs` table
            #       to avoid creating orphan AISummary records on retry.
            article.analysis_status = AnalysisStatus.FAILED
            article.ai_summary = AISummary(analysis_error=str(err))
            await db.commit()
            logger.exception("Analysis failed for article %s", article.id)

    await asyncio.sleep(settings.WORKER_SLEEP_SECONDS)

async def main() -> None:
    mq = MessageQueue(settings.RABBITMQ_URL)
    await mq.connect()
    try:
        await mq.consume(QUEUE_NAME, process_analysis)
    finally:
        await mq.close()

if __name__ == "__main__":
    asyncio.run(main())
