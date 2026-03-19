from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime


class WalletBalance(BaseModel):
    address: str
    ton_balance: float
    ton_balance_raw: str
    usd_value: float
    ton_price_usd: float
    status: str
    name: Optional[str] = None
    icon: Optional[str] = None
    is_scam: bool = False
    error: Optional[str] = None


class JettonBalance(BaseModel):
    symbol: str
    name: str
    balance: float
    balance_raw: str
    decimals: int
    usd_value: Optional[float] = None
    address: str
    image: Optional[str] = None
    verified: bool = False


class WalletOverview(BaseModel):
    """Full wallet overview — TON + all tokens."""
    ton: WalletBalance
    jettons: List[JettonBalance]
    total_usd: float          # TON + jettons combined
    has_wallet: bool          # False if user hasn't connected a wallet
    network: str              # "mainnet" or "testnet"


class Transaction(BaseModel):
    hash: str
    lt: int
    type: str
    direction: str             # "in" | "out" | "self"
    title: str
    time_unix: int
    time_iso: str
    amount_ton: Optional[float] = None
    amount_usd: Optional[float] = None
    token_symbol: Optional[str] = None
    token_amount: Optional[float] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    comment: Optional[str] = None
    fee_ton: float
    status: str
    explorer_url: str


class TransactionHistory(BaseModel):
    transactions: List[Transaction]
    address: str
    has_more: bool
    next_lt: Optional[int] = None


class DepositInfo(BaseModel):
    raw_form: str
    bounceable: str
    non_bounceable: str
    given: str
    ton_link: str
    qr_value: str
