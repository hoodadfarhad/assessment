# advisor-accounts — seed repository

A small FastAPI + SQLite service for advisor client accounts, positions and transfers. The full task is in the challenge document on tenx.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                      # some tests fail on purpose
python seed_db.py           # optional: sample database for local runs
uvicorn app.main:app --reload
```

Tests use a temporary database per test (see `tests/conftest.py`); they never touch `advisor.db`.

## Layout

| Path | Contents |
| --- | --- |
| `app/main.py` | Application and router registration |
| `app/db.py` | Schema, connection, `get_conn` dependency |
| `app/models.py` | Request and response models |
| `app/routes/accounts.py` | `GET /accounts/{id}`, `GET /accounts/{id}/positions` |
| `app/routes/transfers.py` | `POST /transfers` |
| `docs/TKT-212.md` | The ticket for Assignment 2, Part A |
| `review/pr_17.diff` | The teammate pull request for Assignment 2, Part B |
| `seed_db.py` | Creates a sample `advisor.db` |

## API conventions

- Money is returned as a string with exactly two decimals, e.g. `"1250.00"`.
- `POST /transfers` accepts `{"from_account", "to_account", "amount"}` and an optional `Idempotency-Key` header. A repeated request with the same key must not move money twice and must return the original response.
- Timestamps are stored and returned as ISO 8601 in UTC.

## Rules

- Do not delete, skip or weaken existing tests. Add tests freely.
- Keep existing response shapes unchanged.
