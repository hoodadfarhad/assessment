from typing import Literal

from pydantic import BaseModel


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float


class TransferResponse(BaseModel):
    transfer_id: str
    from_balance: str
    to_balance: str


TransactionType = Literal["deposit", "withdrawal", "transfer_in", "transfer_out"]


class TransactionItem(BaseModel):
    id: int
    type: TransactionType
    amount: str
    created_at: str


class TransactionListResponse(BaseModel):
    items: list[TransactionItem]
    next_cursor: str | None
