# JWT Authentication — How It Works

## The Core Idea: Stateless Auth

This backend uses **JSON Web Tokens (JWT)**, which means Django does **not** maintain any ongoing "connection" or session with the browser after login. There is no database row tracking who is logged in.

Instead, at login Django hands the frontend a signed token. From that point on, Django simply reads and verifies the token on every request — no DB lookup, no connection needed.

Compare this to the old session model:

|                    | Session Auth (old)                            | JWT Auth (current)                             |
| ------------------ | --------------------------------------------- | ---------------------------------------------- |
| Storage            | Django stores a session record in DB/cache    | Django stores nothing                          |
| Each request       | Client sends cookie → Django looks up session | Client sends token → Django verifies signature |
| Server dependency  | Stateful (coupled)                            | Stateless (independent)                        |
| Expiry enforcement | Server can invalidate sessions                | Token expires by its own timestamp             |

---

## Step-by-Step Flow

### 1. Login

```
POST /auth/login/
Body: { "email": "user@example.com", "password": "..." }

Response 200:
{
  "access":  "<access_token>",   // valid for 12 hours
  "refresh": "<refresh_token>"   // valid for 7 days
}
```

The frontend receives two tokens:

- **Access token** — short-lived (12 hours). Used on every API request.
- **Refresh token** — long-lived (7 days). Used only to get a new access token.

---

### 2. Authenticated Requests

For every API call that requires authentication, the frontend attaches the access token in the `Authorization` header:

```
GET /api/articles/
Authorization: Bearer <access_token>
```

Django receives this, verifies the signature using its secret key, extracts the user identity from the token payload, and processes the request — all without touching the database.

---

### 3. When the Access Token Expires (after 12h)

The frontend should catch a `401 Unauthorized` response and automatically exchange the refresh token for a new access token:

```
POST /auth/token/refresh/
Body: { "refresh": "<refresh_token>" }

Response 200:
{
  "access": "<new_access_token>"
}
```

This endpoint is provided by `djangorestframework-simplejwt` automatically. No new login is required.

If the refresh token itself is expired (after 7 days), the user must log in again.

---

### 4. Logout

JWT logout is **client-side only**. Because Django is stateless, there is no session to destroy on the server. The client simply deletes both tokens from storage.

```
// Example (JavaScript)
localStorage.removeItem("access_token");
localStorage.removeItem("refresh_token");
// Redirect to login
```

> Note: `POST /auth/logout/` still exists to clear any legacy Django session cookie if present, but it has no effect on JWT tokens.

---

## Where to Store Tokens (Security)

| Storage                 | Security | Notes                                                      |
| ----------------------- | -------- | ---------------------------------------------------------- |
| `localStorage`          | Low      | Vulnerable to XSS attacks — avoid for sensitive apps       |
| `sessionStorage`        | Medium   | Cleared on tab close; still XSS-accessible                 |
| `httpOnly` cookie       | High     | Not accessible to JavaScript — best protection against XSS |
| In-memory (React state) | High     | Lost on page refresh; must refresh from cookie or re-login |

**Recommendation**: Store the refresh token in an `httpOnly` cookie set by the backend at login. Store the access token in memory (a React context or state variable). This prevents XSS from stealing long-lived credentials.

---

## Token Lifetimes (Current Config)

| Token         | Lifetime                   |
| ------------- | -------------------------- |
| Access token  | 12 hours                   |
| Refresh token | 7 days (simplejwt default) |

These are configured in `src/config/settings.py` inside `SIMPLE_JWT`.

---

## Rate Limiting

The `/auth/login/` and `/auth/password-reset/` endpoints are rate-limited to **10 requests/minute per IP** in production to prevent brute-force attacks. This limit is configured via `DEFAULT_THROTTLE_RATES` in `settings.py`.
