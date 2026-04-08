"""Authentication and user-management operations for database layer."""

from __future__ import annotations

import secrets
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import config
import database


def _norm_username(username: str) -> str:
    return (username or "").strip().lower()


def _utcnow_naive() -> datetime:
    """UTC now as naive datetime for sqlite text storage/comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utcnow() -> datetime:
    """UTC now with timezone info."""
    return datetime.now(timezone.utc)


def create_admin_user(username: str, password: str) -> None:
    """Create admin user if not exists."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.table("users").select("id").eq("username", username).execute()
        if not result.data:
            password_hash = database._hash_password(password)
            supabase.table("users").insert(
                {"username": username, "password_hash": password_hash, "role": "admin"}
            ).execute()
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone() is None:
                password_hash = database._hash_password(password)
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role)
                    VALUES (?, ?, 'admin')
                    """,
                    (username, password_hash),
                )
                conn.commit()


def verify_user(username: str, password: str) -> Optional[Dict]:
    """Verify user credentials using secure password verification."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.table("users").select("*").eq("username", username).execute()

        if not result.data:
            return None

        row = result.data[0]
        if database._verify_password(password, row["password_hash"]):
            row.pop("password_hash", None)
            if row.get("location_id"):
                loc_result = (
                    supabase.table("locations")
                    .select("name")
                    .eq("id", row["location_id"])
                    .execute()
                )
                if loc_result.data:
                    row["location_name"] = loc_result.data[0]["name"]
            return row
        return None
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.*, l.name as location_name
                FROM users u
                LEFT JOIN locations l ON u.location_id = l.id
                WHERE u.username = ?
                """,
                (username,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        if database._verify_password(password, row["password_hash"]):
            user = dict(row)
            user.pop("password_hash", None)
            return user
        return None


def get_all_users() -> List[Dict]:
    """Return all users (password_hash excluded)."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("users")
            .select("id, username, email, role, location_id, created_at")
            .order("username")
            .execute()
        )
        users = []
        for row in result.data:
            if "locations" in row:
                row["location_name"] = (
                    row.pop("locations", {}).get("name")
                    if isinstance(row.get("locations"), dict)
                    else None
                )
            else:
                row["location_name"] = None
            users.append(row)
        return users
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.id, u.username, u.email, u.role, u.location_id,
                       u.created_at, l.name AS location_name
                FROM users u
                LEFT JOIN locations l ON u.location_id = l.id
                ORDER BY u.username
                """
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]


def create_user(
    username: str,
    password: str,
    role: str = "manager",
    location_id: Optional[int] = None,
    email: str = "",
) -> Tuple[bool, str]:
    """Create a new user. Returns (success, message)."""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return (
            False,
            f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters.",
        )
    if not username.strip():
        return False, "Username cannot be empty."

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("users")
            .select("id")
            .eq("username", username.strip())
            .execute()
        )
        if result.data:
            return False, f"Username '{username}' already exists."
        pw_hash = database._hash_password(password)
        supabase.table("users").insert(
            {
                "username": username.strip(),
                "password_hash": pw_hash,
                "email": email.strip(),
                "role": role,
                "location_id": location_id,
            }
        ).execute()
        return True, f"User '{username}' created."
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM users WHERE username = ?", (username.strip(),)
            )
            if cursor.fetchone():
                return False, f"Username '{username}' already exists."
            pw_hash = database._hash_password(password)
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, email, role, location_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username.strip(), pw_hash, email.strip(), role, location_id),
            )
            conn.commit()
        return True, f"User '{username}' created."


def update_user(
    user_id: int,
    role: Optional[str] = None,
    location_id: Optional[int] = None,
    email: Optional[str] = None,
    new_password: Optional[str] = None,
) -> Tuple[bool, str]:
    """Update role, location, email, and/or password for an existing user."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("users").select("id, username").eq("id", user_id).execute()
        )
        if not result.data:
            return False, "User not found."
        username = result.data[0]["username"]

        updates = {}
        if role is not None:
            updates["role"] = role
        if location_id is not None:
            updates["location_id"] = location_id
        if email is not None:
            updates["email"] = email
        if new_password is not None:
            if len(new_password) < config.MIN_PASSWORD_LENGTH:
                return (
                    False,
                    f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters.",
                )
            updates["password_hash"] = database._hash_password(new_password)

        if updates:
            supabase.table("users").update(updates).eq("id", user_id).execute()
        return True, f"User '{username}' updated."
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return False, "User not found."
            username = row["username"]
            if role is not None:
                cursor.execute(
                    "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
                )
            if location_id is not None:
                cursor.execute(
                    "UPDATE users SET location_id = ? WHERE id = ?",
                    (location_id, user_id),
                )
            if email is not None:
                cursor.execute(
                    "UPDATE users SET email = ? WHERE id = ?", (email, user_id)
                )
            if new_password is not None:
                if len(new_password) < config.MIN_PASSWORD_LENGTH:
                    return (
                        False,
                        f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters.",
                    )
                pw_hash = database._hash_password(new_password)
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (pw_hash, user_id),
                )
            conn.commit()
        return True, f"User '{username}' updated."


def delete_user(user_id: int, current_username: str) -> Tuple[bool, str]:
    """Delete a user. Prevents deleting yourself."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = supabase.table("users").select("username").eq("id", user_id).execute()
        if not result.data:
            return False, "User not found."
        username = result.data[0]["username"]
        if username == current_username:
            return False, "You cannot delete your own account."
        supabase.table("users").delete().eq("id", user_id).execute()
        return True, f"User '{username}' deleted."
    else:
        with database.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return False, "User not found."
            if row["username"] == current_username:
                return False, "You cannot delete your own account."
            uname = row["username"]
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        return True, f"User '{uname}' deleted."


def create_user_session(user_id: int, days: int = 30) -> str:
    """Generate and persist a secure session token. Returns token string."""
    token = secrets.token_hex(32)
    token_hash = database._hash_session_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    if database.use_supabase():
        supabase = database.get_supabase_client()
        supabase.table("user_sessions").insert(
            {"token": token_hash, "user_id": user_id, "expires_at": expires_at}
        ).execute()
    else:
        with database.db_connection() as conn:
            conn.execute(
                "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )
            conn.commit()
    return token


def validate_session_token(token: str) -> Optional[Dict]:
    """Return user dict for a valid non-expired token, or None."""
    if not token:
        return None
    token_hash = database._hash_session_token(token)

    if database.use_supabase():
        supabase = database.get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()
        result = (
            supabase.table("user_sessions")
            .select("user_id, expires_at")
            .eq("token", token_hash)
            .execute()
        )

        if not result.data:
            return None

        expires_at = result.data[0]["expires_at"]
        if expires_at <= now:
            return None

        user_id = result.data[0]["user_id"]
        user_result = supabase.table("users").select("*").eq("id", user_id).execute()

        if not user_result.data:
            return None

        user = user_result.data[0]
        user.pop("password_hash", None)

        if user.get("location_id"):
            loc_result = (
                supabase.table("locations")
                .select("name")
                .eq("id", user["location_id"])
                .execute()
            )
            if loc_result.data:
                user["location_name"] = loc_result.data[0]["name"]

        return user
    else:
        with database.db_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.email,
                    u.role,
                    u.location_id,
                    u.created_at,
                    l.name AS location_name
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                LEFT JOIN locations l ON l.id = u.location_id
                WHERE s.token = ?
                  AND s.expires_at > datetime('now')
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row else None


def delete_session_token(token: str) -> None:
    """Remove a session token on logout."""
    if not token:
        return
    token_hash = database._hash_session_token(token)
    if database.use_supabase():
        supabase = database.get_supabase_client()
        supabase.table("user_sessions").delete().eq("token", token_hash).execute()
    else:
        with database.db_connection() as conn:
            conn.execute(
                "DELETE FROM user_sessions WHERE token = ?",
                (token_hash,),
            )
            conn.commit()


def purge_expired_sessions() -> None:
    """Delete all expired sessions."""
    if database.use_supabase():
        supabase = database.get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("user_sessions").delete().lt("expires_at", now).execute()
    else:
        with database.db_connection() as conn:
            conn.execute(
                "DELETE FROM user_sessions WHERE expires_at <= datetime('now')"
            )
            conn.commit()


def is_login_locked(username: str) -> Tuple[bool, int]:
    """Return whether username is locked and remaining lock minutes."""
    un = _norm_username(username)
    if not un:
        return False, 0

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("auth_login_attempts")
            .select("failed_count, locked_until")
            .eq("username", un)
            .execute()
        )

        if not result.data:
            return False, 0

        row = result.data[0]
        locked_until = row.get("locked_until")
        if not locked_until:
            return False, 0

        now = datetime.now(timezone.utc)
        until = datetime.fromisoformat(locked_until.replace("Z", "+00:00"))
        if until <= now:
            supabase.table("auth_login_attempts").update(
                {"failed_count": 0, "locked_until": None}
            ).eq("username", un).execute()
            return False, 0

        remaining = max(1, int(math.ceil((until - now).total_seconds() / 60.0)))
        return True, remaining
    else:
        with database.db_connection() as conn:
            row = conn.execute(
                """
                SELECT failed_count, locked_until
                FROM auth_login_attempts
                WHERE username = ?
                """,
                (un,),
            ).fetchone()

            if not row:
                return False, 0

            locked_until = row["locked_until"]
            if not locked_until:
                return False, 0

            now = _utcnow_naive()
            until = datetime.strptime(str(locked_until), "%Y-%m-%d %H:%M:%S")
            if until <= now:
                conn.execute(
                    """
                    UPDATE auth_login_attempts
                    SET failed_count = 0, locked_until = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE username = ?
                    """,
                    (un,),
                )
                conn.commit()
                return False, 0

            remaining = max(1, int(math.ceil((until - now).total_seconds() / 60.0)))
            return True, remaining


def record_failed_login(username: str) -> Tuple[bool, int]:
    """Increment failed login count and lock user temporarily if threshold reached."""
    un = _norm_username(username)
    if not un:
        return False, 0

    locked, mins = is_login_locked(un)
    if locked:
        return True, mins

    if database.use_supabase():
        supabase = database.get_supabase_client()
        result = (
            supabase.table("auth_login_attempts")
            .select("failed_count")
            .eq("username", un)
            .execute()
        )
        failed = result.data[0]["failed_count"] if result.data else 0
        failed += 1

        locked_until = None
        if failed >= int(config.MAX_LOGIN_ATTEMPTS):
            locked_until = (
                _utcnow() + timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
            ).isoformat()

        if result.data:
            supabase.table("auth_login_attempts").update(
                {"failed_count": failed, "locked_until": locked_until}
            ).eq("username", un).execute()
        else:
            supabase.table("auth_login_attempts").insert(
                {"username": un, "failed_count": failed, "locked_until": locked_until}
            ).execute()

        return is_login_locked(un)
    else:
        with database.db_connection() as conn:
            row = conn.execute(
                "SELECT failed_count FROM auth_login_attempts WHERE username = ?",
                (un,),
            ).fetchone()
            failed = int(row["failed_count"]) if row else 0
            failed += 1

            locked_until = None
            if failed >= int(config.MAX_LOGIN_ATTEMPTS):
                locked_until = (
                    _utcnow_naive() + timedelta(minutes=config.LOGIN_LOCKOUT_MINUTES)
                ).strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                """
                INSERT INTO auth_login_attempts (username, failed_count, locked_until, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(username) DO UPDATE SET
                    failed_count = excluded.failed_count,
                    locked_until = excluded.locked_until,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (un, failed, locked_until),
            )
            conn.commit()

        return is_login_locked(un)


def clear_failed_login(username: str) -> None:
    """Clear failed login tracking for username after successful auth."""
    un = _norm_username(username)
    if not un:
        return
    if database.use_supabase():
        supabase = database.get_supabase_client()
        supabase.table("auth_login_attempts").delete().eq("username", un).execute()
    else:
        with database.db_connection() as conn:
            conn.execute("DELETE FROM auth_login_attempts WHERE username = ?", (un,))
            conn.commit()
