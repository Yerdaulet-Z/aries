import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.worker.client import MessageQueue
from app.api.routes import router, set_message_queue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

mq = MessageQueue(settings.RABBITMQ_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB + connect RabbitMQ. Shutdown: close MQ."""
    await init_db()
    await mq.connect()
    set_message_queue(mq)
    yield
    await mq.close()


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

app.include_router(router)
