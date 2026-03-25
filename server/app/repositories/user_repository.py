from typing import Optional
from sqlalchemy.future import select
from app.repositories.base import BaseRepository
from app.models.user import User as UserModel
from pydantic import BaseModel

class UserCreate(BaseModel):
    telegram_id: Optional[str] = None
    username: Optional[str] = None
    wallet_address: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    wallet_address: Optional[str] = None

class UserRepository(BaseRepository[UserModel, UserCreate, UserUpdate]):
    async def get_by_telegram_id(self, tg_id: str) -> Optional[UserModel]:
        query = select(self.model).where(self.model.telegram_id == tg_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_wallet(self, wallet_address: str) -> Optional[UserModel]:
        query = select(self.model).where(self.model.wallet_address == wallet_address)
        result = await self.db.execute(query)
        return result.scalars().first()
