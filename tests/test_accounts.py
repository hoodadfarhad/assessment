def test_get_account(client):
    r = client.get("/accounts/ACC-1001")
    assert r.status_code == 200
    assert r.json()["client_name"] == "Client One"


def test_get_account_not_found(client):
    assert client.get("/accounts/ACC-9999").status_code == 404


def test_positions_shape(client):
    r = client.get("/accounts/ACC-1001/positions")
    assert r.status_code == 200
    positions = r.json()["positions"]
    assert len(positions) == 6
    assert positions[0] == {"fund_code": "FND-101", "fund_name": "Maple Canadian Equity",
                            "units": "100.0000", "market_value": "2451.00"}


def test_positions_query_count(client, query_log):
    query_log.reset()
    r = client.get("/accounts/ACC-1001/positions")
    assert r.status_code == 200
    assert len(query_log.selects()) <= 2, f"{len(query_log.selects())} SELECT statements for one request"
