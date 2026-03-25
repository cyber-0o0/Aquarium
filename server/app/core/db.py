from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=False,  # Set True only for debug — avoid leaking SQL in production logs
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Alias kept for backward compatibility
SessionLocal = AsyncSessionLocal


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
