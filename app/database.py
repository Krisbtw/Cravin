"""
Cravin — Database Engine & Session Management
Uses async SQLAlchemy with SQLite (dev) or PostgreSQL (prod).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import get_settings

settings = get_settings()

def sanitize_database_url(url: str) -> str:
    """
    Ensure the database URL uses the asyncpg driver for PostgreSQL.
    Converts postgresql:// or postgres:// to postgresql+asyncpg://.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


database_url = sanitize_database_url(settings.database_url)
is_sqlite = "sqlite" in database_url

connect_args = {}
engine_kwargs = {
    "echo": settings.debug,
}

if is_sqlite:
    connect_args["check_same_thread"] = False
else:
    # Disable prepared statement caching for PgBouncer / Supabase / Neon transaction pooling
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    **engine_kwargs,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def get_db():
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables and apply non-destructive column additions."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Safe column migrations for schema additions
            from sqlalchemy import text
            try:
                await conn.execute(text("ALTER TABLE orders ADD COLUMN is_group_order BOOLEAN DEFAULT FALSE"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE order_items ADD COLUMN consumed_quantity INTEGER DEFAULT 1"))
            except Exception:
                pass
    except Exception as e:
        # In serverless / concurrent environments, tables may already exist
        # or another worker may be creating them concurrently.
        print(f"init_db notice (non-fatal): {e}")
