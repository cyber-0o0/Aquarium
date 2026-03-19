from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid
from app.core.db import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_hash = Column(String, unique=True, index=True, nullable=True) # TON tx hash
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    type = Column(String, nullable=False) # send, receive, swap, reward, fee
    amount_ton = Column(String, nullable=False)
    amount_usd = Column(String, nullable=True)
    
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    comment = Column(String(128), nullable=True)
    
    status = Column(String, default="pending") # pending, confirmed, failed
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
