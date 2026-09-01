"""
Cravin — Database Engine & Session Management
Uses async SQLAlchemy with SQLite (dev) or PostgreSQL (prod).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
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

engine = create_async_engine(
    database_url,
    echo=settings.debug,
    # SQLite needs this for async
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
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
    """Create all tables. Called on app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
