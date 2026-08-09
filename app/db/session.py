from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import Base

# TODO: Add connection pool tuning for production (pool_size, max_overflow, pool_recycle).
#       Default pool of 5 connections may be insufficient under high concurrency.
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# TODO: Use Alembic for schema migrations in production instead of create_all() + raw DDL.
#       create_all() cannot alter existing columns, add new constraints, or rename tables.
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stage in ["EXTRACTING_TEXT", "GENERATING_SUMMARY", "SAVING_RESULTS"]:
            await conn.execute(text(f"ALTER TYPE analysis_status_enum ADD VALUE IF NOT EXISTS '{stage}';"))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_articles_fts
            ON articles
            USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
        """))
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = timezone('utc', now());
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
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
    async with AsyncSessionLocal() as session:
        yield session
