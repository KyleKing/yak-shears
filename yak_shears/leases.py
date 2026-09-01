"""Content fingerprints that make a write conditional on the version it started from."""

from hashlib import sha256

LEASE_LENGTH = 16


def yak_lease(content: str) -> str:
    """Fingerprint content so a save can prove which version it started from.

    Returns:
        A short hex digest of the content.
    """
    return sha256(content.encode("utf-8")).hexdigest()[:LEASE_LENGTH]
