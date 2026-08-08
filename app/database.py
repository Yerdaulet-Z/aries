from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """
    Create all tables and apply idempotent raw SQL migrations:
    1. GIN full-text search index on title + description
    2. Trigger function for automatic updated_at timestamp
    3. Trigger binding on the articles table
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # GIN index for fast full-text search across title and description
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_articles_fts
            ON articles
            USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
        """))

        # Reusable trigger function: sets updated_at = now() on any row update
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))

        # Bind trigger to articles table (idempotent: drop + create)
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS trg_articles_updated_at ON articles;
        """))
        await conn.execute(text("""
            CREATE TRIGGER trg_articles_updated_at
            BEFORE UPDATE ON articles
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """))


async def get_db():
    """FastAPI dependency — yields an async database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
