# Notes

## What I don't trust

I would re-check the transaction list before shipping. The cursor is a homemade base64 JSON blob; I would confirm clients treat it as opaque and that a well-formed cursor from another filter/account cannot be reused to leak or skip rows. Date filters use `substr(created_at, 1, 10)`, which is only the UTC date if every stored timestamp is UTC ISO-8601 with a `YYYY-MM-DD` prefix. Pagination tests insert rows sequentially; I did not prove concurrent writes or mixed timestamp formats. Ledger/search in `REVIEW.md` was read from a diff, not a running branch—line numbers and whether `/accounts/search` actually wins routing should be confirmed against the real files. Existing transfers still persist money as SQLite `REAL`.

## AI use

I used a mix of ChatGPT and Cursor.
