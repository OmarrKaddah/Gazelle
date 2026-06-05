# src/auth.py

Authentication primitives for the FastAPI chat backend: password hashing, bearer-token login/logout, and the FastAPI dependency that resolves a request's `Authorization: Bearer <token>` header into a current-user dict.

## Line-by-line

**Lines 1-10 — imports**

- `hashlib` for SHA-256 token hashing.
- `secrets.token_urlsafe` for cryptographically random session tokens.
- `bcrypt` for password hashing (uses adaptive cost via `bcrypt.gensalt()`).
- FastAPI's `Depends` and `HTTPException` for dependency-injection plumbing.
- `HTTPAuthorizationCredentials, HTTPBearer` parses the `Authorization` header.
- `AsyncSession` is the SQLAlchemy async session type used in type hints.
- Repository functions (`createSession`, etc.) handle the actual PostgreSQL reads/writes.
- `getDbSession` is the FastAPI dependency that yields one async DB session per request.

**Line 13 — bearer scheme**

`bearer = HTTPBearer(auto_error=False)`. The `auto_error=False` is important: it makes FastAPI return `None` instead of raising 403 when the header is missing, so `getCurrentUser` can produce a properly-worded 401 below.

**Lines 16-17 — `hashToken(token)`**

SHA-256 of the token's UTF-8 bytes, hex-encoded. The plaintext token goes out to the client once; only the hash is stored in PostgreSQL, so a DB leak doesn't expose live tokens.

**Lines 20-21 — `verifyPassword(password, passwordHash)`**

Wraps `bcrypt.checkpw`. Both arguments must be `bytes`, so the strings are encoded to UTF-8 first.

**Lines 24-33 — `login(username, password, session)`**

- `getUserByUsername` does a SELECT for the user row.
- The combined `if not user or not verifyPassword(...)` returns `None` for both "no such user" and "wrong password" — same response on purpose so attackers can't enumerate usernames.
- `secrets.token_urlsafe(32)` generates a 32-byte (~43 character) URL-safe random token.
- `createSession` inserts a row recording the user id and the token's hash.
- `await session.commit()` persists the new session row.
- The plaintext token is returned to the caller — this is the only time it exists outside the client.

**Lines 36-38 — `logout(token, session)`**

Hashes the token to find the matching session row, deletes it, commits. The plaintext is hashed locally because the DB only knows hashes.

**Lines 41-51 — `userFromToken(token, session)`**

- `getUserByTokenHash` joins through the session row to return the owning User.
- Returns `None` if no session matches the hash (expired or never existed).
- Otherwise returns a small dict with stringified id, username (used twice — once as `username`, once as `name`), role, and clearance level. The clearance value drives `docAccess.py` filtering downstream.

**Lines 54-63 — `getCurrentUser` dependency**

The FastAPI dependency every authenticated route depends on.

- `creds: HTTPAuthorizationCredentials = Depends(bearer)` runs the bearer scheme on the incoming request; resolves to `None` if no `Authorization` header.
- `session: AsyncSession = Depends(getDbSession)` opens a per-request DB session.
- Missing credentials → 401 with `"Missing credentials"`.
- Invalid or expired token → 401 with `"Invalid or expired token"`. The two distinct messages help legitimate clients diagnose login state without leaking which users exist.
- Otherwise the user dict from `userFromToken` becomes the `user` parameter of any route that depends on `getCurrentUser`.
