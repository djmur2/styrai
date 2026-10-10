"""Password hashing and HTTP Basic-auth configuration for StyrAI staging."""

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
from collections.abc import Mapping, Sequence


ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
MINIMUM_ITERATIONS = 600_000
MAXIMUM_ITERATIONS = 5_000_000
SALT_BYTES = 16


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
