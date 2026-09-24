def _transfer(client, amount, key=None, src="ACC-1001", dst="ACC-1002"):
    headers = {"Idempotency-Key": key} if key else {}
    return client.post("/transfers", json={"from_account": src, "to_account": dst, "amount": amount}, headers=headers)


def test_transfer_moves_money(client):
    r = _transfer(client, 250)
    assert r.status_code == 201
    assert client.get("/accounts/ACC-1001").json()["balance"] == "750.00"
    assert client.get("/accounts/ACC-1002").json()["balance"] == "750.00"


def test_transfer_insufficient_funds(client):
    assert _transfer(client, 5000).status_code == 409


def test_transfer_unknown_account(client):
    assert _transfer(client, 10, dst="ACC-9999").status_code == 404


def test_transfer_precision(client):
    for _ in range(10):
        assert _transfer(client, 0.10).status_code == 201
    assert client.get("/accounts/ACC-1001").json()["balance"] == "999.00"
    assert client.get("/accounts/ACC-1002").json()["balance"] == "501.00"


def test_transfer_idempotency_key(client):
    first = _transfer(client, 100, key="retry-abc-123")
    second = _transfer(client, 100, key="retry-abc-123")
    assert first.status_code == 201
    assert second.json()["transfer_id"] == first.json()["transfer_id"]
    assert client.get("/accounts/ACC-1001").json()["balance"] == "900.00"
