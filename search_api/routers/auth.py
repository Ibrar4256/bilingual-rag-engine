"""
POST /auth/login (R26)

Basic auth for the Admin UI — bcrypt password verification, JWT token
issuance. No registration endpoint; the admin user is seeded via env vars.
Search API endpoints do NOT require auth (SPEC.md §3, explicit client gap).
"""

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from pydantic import BaseModel, Field

from search_api.db import get_connection

router = APIRouter(prefix="/auth", tags=["auth"])

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET or JWT_SECRET == "change-me-to-a-random-string":
    import secrets
    JWT_SECRET = secrets.token_urlsafe(32)
    logger.warning("JWT_SECRET not set or is default — generated ephemeral secret (tokens won't survive restarts)")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 8

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

security = HTTPBearer()

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300
_login_attempts: dict[str, list[float]] = defaultdict(list)


def _check_login_rate(key: str) -> None:
    now = time.time()
    cutoff = now - LOGIN_LOCKOUT_SECONDS
    attempts = [t for t in _login_attempts[key] if t > cutoff]
    _login_attempts[key] = attempts
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {LOGIN_LOCKOUT_SECONDS // 60} minutes.",
        )


def _record_login_attempt(key: str) -> None:
    _login_attempts[key].append(time.time())


def _ensure_users_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.commit()


def _authenticate_user(username: str, password: str) -> str | None:
    try:
        conn = get_connection()
        try:
            _ensure_users_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash, role FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
            if row and bcrypt.checkpw(password.encode(), row[0].encode()):
                return row[1]
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"DB auth check failed: {e}")

    if username == ADMIN_USERNAME and ADMIN_PASSWORD_HASH:
        if bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode()):
            return "admin"
    return None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = "admin"


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, request: Request) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{req.username}"
    _check_login_rate(rate_key)

    role = _authenticate_user(req.username, req.password)
    if not role:
        _record_login_attempt(rate_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _login_attempts.pop(rate_key, None)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": req.username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    logger.info(f"EVIDENCE_AUTH_LOGIN: user={req.username}")

    return LoginResponse(
        access_token=token,
        expires_in=JWT_EXPIRY_HOURS * 3600,
    )


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def seed_admin_user():
    """Create the default admin user from env vars if the users table is empty."""
    if not ADMIN_PASSWORD_HASH:
        return
    try:
        conn = get_connection()
        try:
            _ensure_users_table(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                if cur.fetchone()[0] == 0:
                    cur.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                        (ADMIN_USERNAME, ADMIN_PASSWORD_HASH, "admin"),
                    )
                    conn.commit()
                    logger.info(f"EVIDENCE_AUTH_SEED: seeded default admin user '{ADMIN_USERNAME}'")
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"Could not seed admin user: {e}")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: str


@router.get("/users", response_model=list[UserResponse])
def list_users(admin: str = Depends(require_admin)):
    conn = get_connection()
    try:
        _ensure_users_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role, created_at FROM users ORDER BY id")
            rows = cur.fetchall()
        return [
            UserResponse(id=r[0], username=r[1], role=r[2], created_at=str(r[3]))
            for r in rows
        ]
    finally:
        conn.close()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(req: CreateUserRequest, admin: str = Depends(require_admin)):
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    try:
        _ensure_users_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE username = %s", (req.username,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Username already exists")
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING id, created_at",
                (req.username, hashed, req.role),
            )
            row = cur.fetchone()
            conn.commit()
        logger.info(f"EVIDENCE_AUTH_CREATE_USER: admin={admin} created user={req.username}")
        return UserResponse(id=row[0], username=req.username, role=req.role, created_at=str(row[1]))
    finally:
        conn.close()


@router.delete("/users/{username}", status_code=204)
def delete_user(username: str, admin: str = Depends(require_admin)):
    if username == admin:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (username,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")
            conn.commit()
        logger.info(f"EVIDENCE_AUTH_DELETE_USER: admin={admin} deleted user={username}")
    finally:
        conn.close()
