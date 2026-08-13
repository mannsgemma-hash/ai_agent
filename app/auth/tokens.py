from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import OAuthToken

_GENERATE_HINT = (
    'python -c "from cryptography.fernet import Fernet; '
    "print(Fernet.generate_key().decode())\""
)


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError(f"TOKEN_ENCRYPTION_KEY is not set. Generate one:\n  {_GENERATE_HINT}")
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()


def save_token(
    db: Session, provider: str, token: dict, extra: dict | None = None
) -> OAuthToken:
    """Persist an OAuth token response (encrypted). Preserves the existing
    refresh token if the provider didn't return a new one."""
    expires_in = token.get("expires_in")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        if expires_in
        else None
    )

    row = db.query(OAuthToken).filter_by(provider=provider).one_or_none()
    if row is None:
        row = OAuthToken(provider=provider)
        db.add(row)

    row.access_token = encrypt(token["access_token"])
    if token.get("refresh_token"):
        row.refresh_token = encrypt(token["refresh_token"])
    row.expires_at = expires_at
    row.scope = token.get("scope")
    if extra:
        merged = dict(row.extra or {})
        merged.update(extra)
        row.extra = merged

    db.commit()
    db.refresh(row)
    return row


def get_token_row(db: Session, provider: str) -> OAuthToken | None:
    return db.query(OAuthToken).filter_by(provider=provider).one_or_none()
