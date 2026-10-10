"""Password hashing and signed-session configuration for StyrAI staging."""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from collections.abc import Mapping, Sequence


ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
MINIMUM_ITERATIONS = 600_000
MAXIMUM_ITERATIONS = 5_000_000
SALT_BYTES = 16
SESSION_SECRET_ENV = "STYRAI_SESSION_SECRET"
MINIMUM_SESSION_SECRET_BYTES = 32
SESSION_TTL_SECONDS = 8 * 60 * 60


class AuthenticationConfigurationError(ValueError):
    """Raised when hosted-staging authentication is configured unsafely."""


def generate_password_hash(
    password: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """Return a salted PBKDF2-SHA256 password hash suitable for configuration."""

    if not password:
        raise ValueError("Password must not be empty.")
    if not MINIMUM_ITERATIONS <= iterations <= MAXIMUM_ITERATIONS:
        raise ValueError(
            f"PBKDF2 iterations must be between {MINIMUM_ITERATIONS:,} and "
            f"{MAXIMUM_ITERATIONS:,}."
        )
    actual_salt = secrets.token_bytes(SALT_BYTES) if salt is None else salt
    if len(actual_salt) < SALT_BYTES:
        raise ValueError(f"PBKDF2 salt must be at least {SALT_BYTES} bytes.")
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), actual_salt, iterations
    )
    return "$".join(
        (
            ALGORITHM,
            str(iterations),
            base64.urlsafe_b64encode(actual_salt).decode("ascii"),
            base64.urlsafe_b64encode(derived).decode("ascii"),
        )
    )


def _decode_password_hash(encoded: str) -> tuple[int, bytes, bytes]:
    try:
        algorithm, raw_iterations, raw_salt, raw_derived = encoded.split("$", 3)
        iterations = int(raw_iterations)
        salt = base64.b64decode(raw_salt, altchars=b"-_", validate=True)
        derived = base64.b64decode(raw_derived, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise AuthenticationConfigurationError(
            "Password hashes must use pbkdf2_sha256$iterations$salt$digest."
        ) from exc
    if algorithm != ALGORITHM:
        raise AuthenticationConfigurationError(
            f"Password hashes must use {ALGORITHM}."
        )
    if not MINIMUM_ITERATIONS <= iterations <= MAXIMUM_ITERATIONS:
        raise AuthenticationConfigurationError(
            f"PBKDF2 iterations must be between {MINIMUM_ITERATIONS:,} and "
            f"{MAXIMUM_ITERATIONS:,}."
        )
    if len(salt) < SALT_BYTES or len(derived) != hashlib.sha256().digest_size:
        raise AuthenticationConfigurationError(
            "Password hashes must contain a 16-byte-or-longer salt and SHA-256 digest."
        )
    return iterations, salt, derived


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password without ever storing its plaintext representation."""

    iterations, salt, expected = _decode_password_hash(encoded)
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual, expected)


def load_auth_users(
    raw: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load and validate the optional username-to-password-hash mapping."""

    if raw is None:
        source = os.environ if environ is None else environ
        raw = source.get("STYRAI_AUTH_USERS_JSON")
    if raw is None:
        return {}
    if not raw.strip():
        raise AuthenticationConfigurationError(
            "STYRAI_AUTH_USERS_JSON is set but empty."
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthenticationConfigurationError(
            "STYRAI_AUTH_USERS_JSON must be a JSON object."
        ) from exc
    if not isinstance(payload, dict) or not payload:
        raise AuthenticationConfigurationError(
            "STYRAI_AUTH_USERS_JSON must map at least one username to a password hash."
        )

    users: dict[str, str] = {}
    for raw_username, raw_hash in payload.items():
        if not isinstance(raw_username, str) or not raw_username.strip():
            raise AuthenticationConfigurationError("Authentication usernames cannot be empty.")
        username = raw_username.strip()
        if username != raw_username or ":" in username or any(
            character in username for character in "\r\n"
        ):
            raise AuthenticationConfigurationError(
                "Authentication usernames cannot contain whitespace padding, colons, or newlines."
            )
        if not isinstance(raw_hash, str):
            raise AuthenticationConfigurationError(
                f"Authentication entry for {username!r} must be an encoded password hash."
            )
        _decode_password_hash(raw_hash)
        users[username] = raw_hash
    return users


def load_session_secret(
    raw: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    required: bool = False,
) -> bytes | None:
    """Load a high-entropy secret used to sign browser session cookies.

    Authentication-enabled deployments fail closed when the secret is absent or
    too short. Keeping this separate from password hashes allows either value to
    be rotated without treating the password verifier as a signing key.
    """

    if raw is None:
        source = os.environ if environ is None else environ
        raw = source.get(SESSION_SECRET_ENV)
    if raw is None:
        if required:
            raise AuthenticationConfigurationError(
                f"{SESSION_SECRET_ENV} is required when authentication is enabled."
            )
        return None
    if raw != raw.strip() or any(character in raw for character in "\r\n\x00"):
        raise AuthenticationConfigurationError(
            f"{SESSION_SECRET_ENV} cannot contain padding whitespace or control characters."
        )
    encoded = raw.encode("utf-8")
    if len(encoded) < MINIMUM_SESSION_SECRET_BYTES:
        raise AuthenticationConfigurationError(
            f"{SESSION_SECRET_ENV} must contain at least "
            f"{MINIMUM_SESSION_SECRET_BYTES} bytes."
        )
    return encoded


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _urlsafe_encode(decoded) != value:
        raise ValueError("Non-canonical URL-safe base64 encoding.")
    return decoded


def create_session_token(
    username: str,
    secret: bytes,
    *,
    now: int | None = None,
    lifetime_seconds: int = SESSION_TTL_SECONDS,
) -> str:
    """Create a compact, HMAC-authenticated session token."""

    if not username or not secret:
        raise ValueError("A username and session secret are required.")
    if len(secret) < MINIMUM_SESSION_SECRET_BYTES:
        raise ValueError(
            f"Session secrets must contain at least {MINIMUM_SESSION_SECRET_BYTES} bytes."
        )
    if lifetime_seconds <= 0:
        raise ValueError("Session lifetime must be positive.")
    issued_at = int(time.time()) if now is None else int(now)
    claims = json.dumps(
        {
            "exp": issued_at + lifetime_seconds,
            "iat": issued_at,
            "n": secrets.token_urlsafe(18),
            "u": username,
            "v": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    payload = _urlsafe_encode(claims)
    signature = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest()
    return f"{payload}.{_urlsafe_encode(signature)}"


def verify_session_token(
    token: str,
    secret: bytes,
    users: Mapping[str, str],
    *,
    now: int | None = None,
    maximum_lifetime_seconds: int = SESSION_TTL_SECONDS,
) -> str | None:
    """Return the authenticated username for a valid, unexpired session token."""

    if (
        not token
        or len(token) > 2048
        or len(secret) < MINIMUM_SESSION_SECRET_BYTES
    ):
        return None
    try:
        payload, separator, raw_signature = token.partition(".")
        if not separator or "." in raw_signature:
            return None
        signature = _urlsafe_decode(raw_signature)
        expected = hmac.new(
            secret, payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_urlsafe_decode(payload))
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return None
    if not isinstance(claims, dict) or claims.get("v") != 1:
        return None
    username = claims.get("u")
    nonce = claims.get("n")
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    if (
        not isinstance(username, str)
        or username not in users
        or not isinstance(nonce, str)
        or len(nonce) < 16
        or not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
    ):
        return None
    current_time = int(time.time()) if now is None else int(now)
    if issued_at > current_time + 60 or expires_at <= current_time:
        return None
    if expires_at <= issued_at or expires_at - issued_at > maximum_lifetime_seconds:
        return None
    return username


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a salted PBKDF2-SHA256 hash for STYRAI_AUTH_USERS_JSON. "
            "The password is read without echo and is never written to disk."
        )
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"PBKDF2 work factor (default: {DEFAULT_ITERATIONS}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    try:
        encoded = generate_password_hash(password, iterations=args.iterations)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
