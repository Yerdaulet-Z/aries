import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.core.rabbitmq import MessageQueue
from app.api.routes import router, set_message_queue
from app.api.views import router as views_router
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

mq = MessageQueue(settings.RABBITMQ_URL)
logger = logging.getLogger(__name__)


import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + connect RabbitMQ + launch background AI worker."""
    await init_db()
    
    _mq = MessageQueue(settings.RABBITMQ_URL)
    await _mq.connect()
    set_message_queue(_mq)
    
    # Start embedded AI worker consumer loop
    worker_mq = MessageQueue(settings.RABBITMQ_URL)
    await worker_mq.connect()
    
    from app.worker.consumer import process_analysis, QUEUE_NAME
    
    async def _start_worker():
        try:
            logger.info("Embedded background AI worker consuming from RabbitMQ...")
            await worker_mq.consume(QUEUE_NAME, process_analysis)
        except Exception as e:
            logger.error("Worker exception: %s", e)

    worker_task = asyncio.create_task(_start_worker())
    logger.info("Application and embedded AI worker started successfully.")
    
    yield
    
    worker_task.cancel()
    await worker_mq.close()
    await _mq.close()


app = FastAPI(
    title="News Analyzer API",
    description="Autonomous news fetching with on-demand AI analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(router)
app.include_router(views_router)
