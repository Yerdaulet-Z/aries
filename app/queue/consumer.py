from __future__ import annotations
import asyncio
import logging
import uuid
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.models import AnalysisStatus, Article, AISummary
from app.queue.client import MessageQueue
from app.services.ai import ai_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
QUEUE_NAME = "article_analysis"

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

        article.analysis_status = AnalysisStatus.PROCESSING
        await db.commit()
        
        try:
            text = "\n".join(part for part in [article.description or "", article.content or ""] if part)
            result, raw_response = await ai_service.analyze(title=article.title, text=text)
            
            article.ai_summary = AISummary(
                summary=result.summary,
                sentiment=result.sentiment,
                sentiment_score=result.sentiment_score,
                ai_raw_response=raw_response
            )
            article.analysis_status = AnalysisStatus.COMPLETED
            await db.commit()
        except Exception as err:
            article.analysis_status = AnalysisStatus.FAILED
            article.ai_summary = AISummary(analysis_error=str(err))
            await db.commit()
            logger.exception("Analysis failed for article %s", article.id)

    await asyncio.sleep(settings.WORKER_SLEEP_SECONDS)

async def main() -> None:
    await init_db()
    mq = MessageQueue(settings.RABBITMQ_URL)
    await mq.connect()
    try:
        await mq.consume(QUEUE_NAME, process_analysis)
    finally:
        await mq.close()

if __name__ == "__main__":
    asyncio.run(main())
