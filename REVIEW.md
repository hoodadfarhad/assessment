# PR #17 Review — Ledger Sync + Client Search

## `app/routes/search.py:14` — blocker

**Problem:** `name` is interpolated directly into the SQL query (`LIKE '%{name}%'`). User input can therefore alter the SQL expression, creating a SQL injection vulnerability.

**Suggested fix:** Use a bound parameter and pass the search pattern as a value:

```python
rows = conn.execute(
    "SELECT id, client_name FROM accounts "
    "WHERE client_name LIKE ? ESCAPE '\\' "
    "ORDER BY client_name "
    "LIMIT 50",
    (_like_pattern(name),),
).fetchall()
```

Escape `\`, `%`, and `_` in the user input before wrapping it with `%...%` so that those characters are treated literally rather than as `LIKE` metacharacters.

---

## `app/routes/search.py:17-18` — should-fix

**Problem:** `except Exception: return {"results": []}` turns database errors, programming errors, and other unexpected failures into a successful `200` response with an empty result set. This hides real failures from both clients and operators.

**Suggested fix:** Let unexpected exceptions propagate so FastAPI returns a `500`. An empty list should only represent a successful search with no matching clients.

---

## `app/routes/search.py:10-14` — should-fix

**Problem:** `name` is required but unconstrained. Inputs such as `name=` or `name=%` can produce a pattern equivalent to `LIKE '%%'`, returning every client. There is also no result limit.

If this endpoint is accessible without appropriate authorization, this creates an especially serious client-data exposure risk.

**Suggested fix:**

* Reject empty input with `422`.
* Reject inputs consisting only of `LIKE` wildcards such as `%` and `_`.
* Escape `\`, `%`, and `_`.
* Add a result cap, e.g. `LIMIT 50`.
* Ensure the endpoint has the appropriate authorization for client data.

---

## `app/routes/transfers.py:42-45` — blocker

**Problem:** The local transfer is committed first, and `post_transfer` runs afterward. If the external ledger call fails after retries, the request returns an error even though the local balances, transfer row, and transactions have already been persisted.

This creates an inconsistent state: the client sees a failed transfer even though money has already moved locally. Retrying the same `POST /transfers` can then apply the local movement again.

There is also a second risk: if the ledger successfully processes a request but the response is lost due to a timeout, the client may retry and cause the external ledger to process the same transfer twice because the request has no stable idempotency key.

**Suggested fix:** Do not treat a committed local database transaction followed by a best-effort HTTP call as one atomic transaction.

The preferred approach is an **outbox pattern**:

1. Persist the transfer and a pending ledger event in the same database transaction.
2. Commit once.
3. A worker sends the ledger event asynchronously.
4. Use `transfer_id` as the ledger idempotency key.
5. Mark the outbox event as completed only after the ledger confirms successful processing.
6. Retry failed events safely using the same idempotency key.

As a narrower alternative, the ledger call could happen before the local commit, but only if the external request is idempotent and failures are handled so the local transaction can be rolled back safely.

**Important:** Never return a `5xx` indicating that a transfer failed after the local money movement has already been committed unless there is a defined reconciliation or compensating mechanism.

---

## `app/services/ledger_client.py:12-21` and `:24-38` — should-fix

**Problem:** `with_retry` retries every `httpx.HTTPError`, including errors caused by `raise_for_status()` for 4xx responses. Most client errors are not transient and will not succeed simply by retrying.

There is also a duplicate-transfer risk when retrying after a timeout: the ledger may have successfully processed the request even though the client never received the response. Without an idempotency key, retrying can create a second ledger entry.

Additionally, `time.sleep()` blocks the worker during each backoff period, while each request can also wait up to five seconds for a timeout.

**Suggested fix:**

* Retry connection errors and timeouts.
* Retry appropriate `5xx` responses.
* Retry `429` only when appropriate, preferably respecting `Retry-After`.
* Do not retry normal `4xx` errors.
* Send a stable idempotency key, such as `transfer_id`, with every ledger request.
* Prefer an async HTTP client or move ledger delivery/retries to a background worker.

---

## `app/services/ledger_client.py:30` — should-fix

**Problem:** `datetime.now().isoformat()` produces a local, naive timestamp. The service convention is ISO-8601 UTC.

**Suggested fix:**

```python
datetime.now(timezone.utc).isoformat(timespec="seconds")
```

This produces an explicit UTC timestamp with the expected timezone information.

---

## `app/services/ledger_client.py:9` and `:35` (`transfers.py:45`) — should-fix

**Problem:** The ledger base URL is hardcoded, making the service difficult to configure across environments.

Also, `str(req.amount)` relies on the representation of the underlying numeric type. For monetary values, this can produce inconsistent serialization such as `"0.1"` instead of `"0.10"` and can expose floating-point representation issues.

The rest of the application represents monetary values as two-decimal strings.

**Suggested fix:**

* Read the ledger base URL from an environment variable/configuration setting.
* Represent monetary values using `Decimal`.
* Quantize to two decimal places and serialize consistently, for example:

```python
amount = amount.quantize(Decimal("0.01"))
amount_str = f"{amount:.2f}"
```

This keeps ledger amounts consistent with the application's existing money representation.

---

## `app/main.py:6` — should-fix

**Problem:** `GET /accounts/search` currently wins over `GET /accounts/{account_id}` because `search.router` is included before the account route.

This means the behavior depends on router registration order. Reordering the router includes could cause `/accounts/search` to be interpreted as an account ID instead.

**Suggested fix:** Define the search route on the accounts router before the dynamic `/{account_id}` route, or use an unambiguous path such as:

```text
GET /search/accounts
```

This removes the dependency on router registration order.

---

# Tests — should-fix

**Problem:** The PR adds no tests covering the new search behavior or the ledger failure scenarios.

Important cases to cover include:

* SQL injection attempts.
* `LIKE` metacharacters such as `%`, `_`, and `\`.
* Empty search strings.
* Wildcard-only input.
* Result-limit enforcement.
* No-match searches returning an empty list.
* Unexpected database errors returning an appropriate server error.
* Ledger failure after a local transfer attempt.
* Retry behavior for timeouts and `5xx`.
* No retries for normal `4xx` responses.
* Repeated requests using the same idempotency key.
* Ledger timeouts where the ledger may have processed the request successfully.

Existing transfer tests should mock the ledger client so that they do not make real network requests.

---

# Decision: Request changes

The two blockers need to be addressed before merging:

1. **Client search must be parameterized and `LIKE`-safe** to prevent SQL injection and uncontrolled result expansion.
2. **The local transfer and external ledger synchronization must have a reliable consistency/idempotency strategy** so the system cannot silently drop, double-apply, or report failure after money has already moved.

The remaining changes improve error handling, retry safety, configuration, timestamp consistency, route stability, and test coverage.
