from datetime import datetime, timedelta, timezone

from app.db import connect
from app.routes.accounts import encode_cursor


def _insert_tx(db_path, account_id, tx_type, amount, created_at):
    conn = connect(db_path)
    cur = conn.execute(
        "INSERT INTO transactions (account_id, type, amount, created_at) VALUES (?, ?, ?, ?)",
        (account_id, tx_type, amount, created_at),
    )
    conn.commit()
    tx_id = cur.lastrowid
    conn.close()
    return tx_id


def _seed_history(db_path, account_id="ACC-1001"):
    start = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
    specs = [
        ("deposit", 100.0, start),
        ("withdrawal", 25.5, start + timedelta(days=1)),
        ("transfer_in", 50.0, start + timedelta(days=2)),
        ("transfer_out", 10.0, start + timedelta(days=2, hours=3)),
        ("deposit", 200.0, start + timedelta(days=3)),
    ]
    ids = []
    for tx_type, amount, ts in specs:
        ids.append(_insert_tx(db_path, account_id, tx_type, amount, ts.isoformat(timespec="seconds")))
    same_ts = (start + timedelta(days=4)).isoformat(timespec="seconds")
    ids.append(_insert_tx(db_path, account_id, "deposit", 1.0, same_ts))
    ids.append(_insert_tx(db_path, account_id, "withdrawal", 2.0, same_ts))
    ids.append(_insert_tx(db_path, account_id, "deposit", 3.0, same_ts))
    return ids


def test_unknown_account_404(client):
    r = client.get("/accounts/ACC-9999/transactions")
    assert r.status_code == 404


def test_invalid_cursor_400(client, db_path):
    _seed_history(db_path)
    assert client.get("/accounts/ACC-1001/transactions", params={"cursor": "not-a-cursor"}).status_code == 400
    assert client.get("/accounts/ACC-1001/transactions", params={"cursor": ""}).status_code == 400
    assert client.get("/accounts/ACC-1001/transactions", params={"cursor": "@@@"}).status_code == 400


def test_invalid_query_params_422(client):
    assert client.get("/accounts/ACC-1001/transactions", params={"type": "interest"}).status_code == 422
    assert client.get("/accounts/ACC-1001/transactions", params={"from": "14-08-2026"}).status_code == 422
    assert client.get("/accounts/ACC-1001/transactions", params={"to": "yesterday"}).status_code == 422
    assert client.get("/accounts/ACC-1001/transactions", params={"limit": 101}).status_code == 422
    assert client.get("/accounts/ACC-1001/transactions", params={"limit": 0}).status_code == 422


def test_empty_history(client):
    r = client.get("/accounts/ACC-1001/transactions")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_newest_first_and_shape(client, db_path):
    _seed_history(db_path)
    r = client.get("/accounts/ACC-1001/transactions")
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert body["next_cursor"] is None
    assert len(items) == 8
    created = [item["created_at"] for item in items]
    ids = [item["id"] for item in items]
    paired = list(zip(created, ids))
    assert paired == sorted(paired, key=lambda p: (p[0], p[1]), reverse=True)
    first = items[0]
    assert set(first) == {"id", "type", "amount", "created_at"}
    assert first["amount"] == "3.00"
    assert first["created_at"].endswith("+00:00")


def test_type_filter(client, db_path):
    _seed_history(db_path)
    r = client.get("/accounts/ACC-1001/transactions", params={"type": "deposit"})
    types = {item["type"] for item in r.json()["items"]}
    assert types == {"deposit"}
    assert len(r.json()["items"]) == 4


def test_date_filters_inclusive(client, db_path):
    _seed_history(db_path)
    r = client.get(
        "/accounts/ACC-1001/transactions",
        params={"from": "2026-08-12", "to": "2026-08-13"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    dates = {item["created_at"][:10] for item in items}
    assert dates <= {"2026-08-12", "2026-08-13"}
    assert "2026-08-12" in dates
    assert "2026-08-13" in dates
    assert all(item["created_at"][:10] >= "2026-08-12" for item in items)
    assert all(item["created_at"][:10] <= "2026-08-13" for item in items)


def test_default_limit_and_max(client, db_path):
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    for i in range(120):
        _insert_tx(
            db_path,
            "ACC-1001",
            "deposit",
            1.0,
            (start + timedelta(minutes=i)).isoformat(timespec="seconds"),
        )
    default = client.get("/accounts/ACC-1001/transactions")
    assert default.status_code == 200
    assert len(default.json()["items"]) == 50
    assert default.json()["next_cursor"] is not None

    capped = client.get("/accounts/ACC-1001/transactions", params={"limit": 100})
    assert len(capped.json()["items"]) == 100
    assert capped.json()["next_cursor"] is not None


def test_cursor_pages_without_skip_or_repeat(client, db_path):
    ids = _seed_history(db_path)
    collected = []
    cursor = None
    while True:
        params = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        r = client.get("/accounts/ACC-1001/transactions", params=params)
        assert r.status_code == 200
        body = r.json()
        collected.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert collected == sorted(ids, reverse=True)
    assert len(collected) == len(set(collected)) == len(ids)
    # Newest first: ids were inserted in chronological order, last id is newest.
    assert collected[0] == max(ids)
    assert collected[-1] == min(ids)


def test_pagination_stable_when_new_rows_arrive(client, db_path):
    start = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
    original_ids = []
    for i in range(7):
        original_ids.append(
            _insert_tx(
                db_path,
                "ACC-1001",
                "deposit",
                10.0 + i,
                (start + timedelta(hours=i)).isoformat(timespec="seconds"),
            )
        )

    first = client.get("/accounts/ACC-1001/transactions", params={"limit": 2})
    assert first.status_code == 200
    first_ids = [item["id"] for item in first.json()["items"]]
    cursor = first.json()["next_cursor"]
    assert cursor is not None

    newer_id = _insert_tx(
        db_path,
        "ACC-1001",
        "deposit",
        999.0,
        datetime(2026, 8, 20, tzinfo=timezone.utc).isoformat(timespec="seconds"),
    )

    collected = list(first_ids)
    while cursor is not None:
        r = client.get("/accounts/ACC-1001/transactions", params={"limit": 2, "cursor": cursor})
        assert r.status_code == 200
        body = r.json()
        page_ids = [item["id"] for item in body["items"]]
        assert newer_id not in page_ids
        collected.extend(page_ids)
        cursor = body["next_cursor"]

    assert collected == sorted(original_ids, reverse=True)
    assert newer_id not in collected

    # New row is visible on a fresh first page.
    fresh = client.get("/accounts/ACC-1001/transactions", params={"limit": 2})
    assert fresh.json()["items"][0]["id"] == newer_id


def test_cursor_from_last_page_is_null(client, db_path):
    _insert_tx(db_path, "ACC-1001", "deposit", 1.0, "2026-08-01T00:00:00+00:00")
    r = client.get("/accounts/ACC-1001/transactions", params={"limit": 10})
    assert r.json()["next_cursor"] is None


def test_valid_cursor_encoding_roundtrip(client, db_path):
    tx_id = _insert_tx(db_path, "ACC-1001", "deposit", 5.0, "2026-08-01T00:00:00+00:00")
    cursor = encode_cursor("2026-08-01T00:00:00+00:00", tx_id)
    r = client.get("/accounts/ACC-1001/transactions", params={"cursor": cursor})
    assert r.status_code == 200
    assert r.json()["items"] == []
