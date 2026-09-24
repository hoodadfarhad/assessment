import base64
import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_conn
from app.models import TransactionListResponse, TransactionType

router = APIRouter()

_CURSOR_KEYS = ("created_at", "id")


def encode_cursor(created_at: str, tx_id: int) -> str:
    payload = json.dumps({"created_at": created_at, "id": tx_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(raw)
        created_at = data["created_at"]
        tx_id = data["id"]
        if not isinstance(created_at, str) or not isinstance(tx_id, int) or isinstance(tx_id, bool):
            raise ValueError
        extra = set(data) - set(_CURSOR_KEYS)
        if extra:
            raise ValueError
        return created_at, tx_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid cursor") from None


@router.get("/accounts/{account_id}")
def get_account(account_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute(
        "SELECT id, client_name, balance FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="account not found")
    return {"id": row["id"], "client_name": row["client_name"], "balance": f"{row['balance']:.2f}"}


@router.get("/accounts/{account_id}/positions")
def get_positions(
    account_id: str,
    conn: sqlite3.Connection = Depends(get_conn),
):
    if conn.execute(
        "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="account not found")

    positions = conn.execute(
        """
        SELECT
            p.fund_code,
            p.units,
            f.name AS fund_name,
            f.nav
        FROM positions p
        JOIN funds f ON f.code = p.fund_code
        WHERE p.account_id = ?
        ORDER BY p.fund_code
        """,
        (account_id,),
    ).fetchall()

    result = []

    for p in positions:
        result.append(
            {
                "fund_code": p["fund_code"],
                "fund_name": p["fund_name"],
                "units": f"{p['units']:.4f}",
                "market_value": f"{p['units'] * p['nav']:.2f}",
            }
        )

    return {"account_id": account_id, "positions": result}


@router.get("/accounts/{account_id}/transactions", response_model=TransactionListResponse)
def get_transactions(
    account_id: str,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    type: TransactionType | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = None,
    conn: sqlite3.Connection = Depends(get_conn),
):
    if conn.execute(
        "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
    ).fetchone() is None:
        raise HTTPException(status_code=404, detail="account not found")

    sql = """
        SELECT id, type, amount, created_at
        FROM transactions
        WHERE account_id = ?
    """
    params: list = [account_id]

    if from_date is not None:
        sql += " AND substr(created_at, 1, 10) >= ?"
        params.append(from_date.isoformat())
    if to_date is not None:
        sql += " AND substr(created_at, 1, 10) <= ?"
        params.append(to_date.isoformat())
    if type is not None:
        sql += " AND type = ?"
        params.append(type)

    if cursor is not None:
        created_at, tx_id = decode_cursor(cursor)
        sql += " AND (created_at < ? OR (created_at = ? AND id < ?))"
        params.extend([created_at, created_at, tx_id])

    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(sql, params).fetchall()
    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        {
            "id": row["id"],
            "type": row["type"],
            "amount": f"{row['amount']:.2f}",
            "created_at": row["created_at"],
        }
        for row in page
    ]
    next_cursor = None
    if has_more and page:
        last = page[-1]
        next_cursor = encode_cursor(last["created_at"], last["id"])

    return {"items": items, "next_cursor": next_cursor}
