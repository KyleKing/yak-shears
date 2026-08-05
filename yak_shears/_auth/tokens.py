"""Signed, stateless session tokens.

The cookie carries the user id and its own expiry, signed with a server secret held
on disk, so a restart or redeploy no longer invalidates every session. A signature
cannot be withdrawn, so explicit logout records the token's id in a revocation file
that is pruned as entries expire.
"""

import hmac
import json
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime
from hashlib import sha256
from os import getenv
from pathlib import Path

from .models import SessionId

DEFAULT_SECRET_PATH = Path(__file__).parents[1] / ".yak-shears-secret"
DEFAULT_REVOCATION_PATH = Path(__file__).parents[1] / ".yak-shears-revoked.json"

SESSION_TTL_SECONDS = int(getenv("YAK_SHEARS_SESSION_DAYS") or 30) * 86400


def _b64encode(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(encoded: str) -> bytes:
    return urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))


class TokenSigner:
    """Issues and verifies session tokens against a persisted secret."""

    def __init__(self, secret_path: Path | None = None, revocation_path: Path | None = None) -> None:
        self._secret_path = secret_path or DEFAULT_SECRET_PATH
        self._revocation_path = revocation_path or DEFAULT_REVOCATION_PATH
        self._secret: bytes | None = None

    @property
    def secret(self) -> bytes:
        """Server signing key, generated on first use if no key exists yet.

        Replacing the key file invalidates every outstanding session.
        """
        if self._secret is None:
            self._secret = self._load_secret()
        return self._secret

    def _load_secret(self) -> bytes:
        if configured := getenv("YAK_SHEARS_SECRET_KEY"):
            return configured.encode("utf-8")
        try:
            # Exclusive create so two workers starting together cannot each install
            # a key and invalidate the other's freshly issued tokens.
            with self._secret_path.open("xb") as handle:
                secret = secrets.token_bytes(32)
                handle.write(secret)
            self._secret_path.chmod(0o600)
        except FileExistsError:
            return self._secret_path.read_bytes()
        return secret

    def _sign(self, payload: str) -> str:
        return _b64encode(hmac.new(self.secret, payload.encode("utf-8"), sha256).digest())

    def issue(self, user_id: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> SessionId:
        """Mint a token for a user, valid for ttl_seconds.

        Returns:
            Signed token suitable for the session cookie.
        """
        expires = int(datetime.now(tz=UTC).timestamp()) + ttl_seconds
        payload = f"{user_id}:{expires}:{secrets.token_hex(8)}"
        return SessionId(f"{_b64encode(payload.encode('utf-8'))}.{self._sign(payload)}")

    def verify(self, token: str) -> str | None:
        """Extract the user id from a token, or None if it is invalid or expired.

        Returns:
            User id when the signature, expiry, and revocation checks all pass.
        """
        encoded_payload, _, signature = token.partition(".")
        if not signature:
            return None
        try:
            payload = _b64decode(encoded_payload).decode("utf-8")
            user_id, expires, token_id = payload.split(":")
            expires_at = int(expires)
        except (ValueError, UnicodeDecodeError):
            return None

        if not hmac.compare_digest(self._sign(payload), signature):
            return None
        if expires_at <= datetime.now(tz=UTC).timestamp():
            return None
        if token_id in self._load_revocations():
            return None
        return user_id

    def revoke(self, token: str) -> None:
        """Record a token as revoked until its own expiry passes."""
        encoded_payload, _, signature = token.partition(".")
        try:
            payload = _b64decode(encoded_payload).decode("utf-8")
            _, expires, token_id = payload.split(":")
            expires_at = int(expires)
        except (ValueError, UnicodeDecodeError):
            return
        if not signature or not hmac.compare_digest(self._sign(payload), signature):
            return

        now = datetime.now(tz=UTC).timestamp()
        revocations = {tid: exp for tid, exp in self._load_revocations().items() if exp > now}
        revocations[token_id] = expires_at
        self._revocation_path.write_text(json.dumps(revocations), encoding="utf-8")
        self._revocation_path.chmod(0o600)

    def rotate(self) -> None:
        """Discard the signing key, invalidating every outstanding token."""
        self._secret = None
        self._secret_path.unlink(missing_ok=True)
        self._revocation_path.unlink(missing_ok=True)

    def _load_revocations(self) -> dict[str, int]:
        try:
            loaded = json.loads(self._revocation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}
