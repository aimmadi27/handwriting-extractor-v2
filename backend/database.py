import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

def _async_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver (Railway provides postgresql://)."""
    return url.replace("postgresql://", "postgresql+asyncpg://", 1) \
              .replace("postgres://", "postgresql+asyncpg://", 1)

DATABASE_URL = _async_url(os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://app:password@localhost:5432/handwriting",
))

engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
