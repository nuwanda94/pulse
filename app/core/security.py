"""API key hashing and generation helpers."""

import hashlib
import secrets


def hash_api_key(raw_key: str) -> str:
    """Return a hex SHA-256 digest of the raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    """Return a new unguessable raw API key (shown to the caller once)."""
    return f"pulse_{secrets.token_urlsafe(32)}"
