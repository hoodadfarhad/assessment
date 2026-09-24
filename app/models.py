from pydantic import BaseModel


class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: float


class TransferResponse(BaseModel):
    transfer_id: str
    from_balance: str
    to_balance: str
