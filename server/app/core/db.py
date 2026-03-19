from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
SessionLocal = AsyncSessionLocal  # Alias for convenience
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
