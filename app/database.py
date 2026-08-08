from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS analysis_status_enum CASCADE;"))
        await conn.execute(text("DROP TYPE IF EXISTS sentiment_enum CASCADE;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_articles_fts
            ON articles
            USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
        """))
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = now();
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
