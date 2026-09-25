"""API key hashing helpers."""

import hashlib


def hash_api_key(raw_key: str) -> str:
    """Return a hex SHA-256 digest of the raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
