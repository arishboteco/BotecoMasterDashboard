"""Authentication and user-management operations for database layer."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import config
import database


def create_admin_user(username: str, password: str) -> None:
    """Create admin user if not exists."""
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
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (username.strip(),))
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
    with database.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "User not found."
        username = row["username"]
        if role is not None:
            cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        if location_id is not None:
            cursor.execute(
                "UPDATE users SET location_id = ? WHERE id = ?", (location_id, user_id)
            )
        if email is not None:
            cursor.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        if new_password is not None:
            if len(new_password) < config.MIN_PASSWORD_LENGTH:
                return (
                    False,
                    f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters.",
                )
            pw_hash = database._hash_password(new_password)
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id)
            )
        conn.commit()
    return True, f"User '{username}' updated."


def delete_user(user_id: int, current_username: str) -> Tuple[bool, str]:
    """Delete a user. Prevents deleting yourself."""
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
            WHERE s.token IN (?, ?)
              AND s.expires_at > datetime('now')
            """,
            (token_hash, token),
        ).fetchone()
    return dict(row) if row else None


def delete_session_token(token: str) -> None:
    """Remove a session token on logout."""
    if not token:
        return
    token_hash = database._hash_session_token(token)
    with database.db_connection() as conn:
        conn.execute(
            "DELETE FROM user_sessions WHERE token IN (?, ?)",
            (token_hash, token),
        )
        conn.commit()


def purge_expired_sessions() -> None:
    """Delete all expired sessions."""
    with database.db_connection() as conn:
        conn.execute("DELETE FROM user_sessions WHERE expires_at <= datetime('now')")
        conn.commit()
