# security_layer — authentication

[← Back to BACKEND.md](../BACKEND.md) · [API reference](security_layer_API_DOCS.md)

Password hashing and JWT issue/verify. Small on purpose.

## The problem

The service is multi-tenant: each user has their own FAISS index and their own
rows in every table. Getting identity wrong means one user's documents surface in
another's answers. Two things must hold:

1. Stored passwords must survive a database disclosure.
2. Every request must prove which user it belongs to, cheaply, without a
   database round-trip on the hot path.

## Design

### Password storage

Argon2 via `passlib`'s `CryptContext`. Argon2 is memory-hard, so GPU and ASIC
attacks gain far less than they do against bcrypt or PBKDF2. Parameters are
encoded in the hash string itself, so raising the cost later does not invalidate
existing hashes — `deprecated="auto"` marks older ones for rehash on next login.

Plaintext passwords are never stored, logged, or returned.

### Tokens

Two token types, distinguished by an explicit `type` claim:

| | Access | Refresh |
|---|---|---|
| Claim | `type: "access"` | `type: "refresh"` |
| Lifetime | minutes (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) | days (`JWT_REFRESH_TOKEN_EXPIRE_DAYS`) |
| Purpose | sent with every request | exchanged for a new access token |

Both carry `sub` (the user UUID) and `iat`. The verify functions check the
`type` claim, so a refresh token cannot be replayed as an access token — the
common failure when both are signed with the same key.

Verification is signature-only: no database lookup, so authorising a request
costs microseconds. The cost is that revocation is not possible before natural
expiry, which is why access-token lifetimes are short.

Errors are distinguished — `TokenExpiredError` (retry after refresh) versus
`InvalidTokenError` (bad signature or malformed) versus `TokenError` (wrong
type) — so callers can respond appropriately instead of treating every failure
as "unauthorised".

## Trade-offs and known gaps

- **No revocation list.** A stolen access token is valid until it expires.
  Mitigated by short lifetimes; a denylist would reintroduce a database hit per
  request.
- **Tokens travel in the JSON body.** `/query` and `/upload` take
  `access_token` as a body field rather than an `Authorization` header, so they
  land in any body-logging middleware and in browser devtools history.
- **`JWT_SECRET_KEY` is not validated at import.** If unset, `jwt.encode` fails
  at first use rather than at startup.
- **No rate limiting.** Nothing throttles login attempts; Argon2's cost is the
  only brute-force defence.
- **No password policy.** Length and complexity are unenforced.
