import unicodedata
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_password_hash = PasswordHash.recommended()

JWT_ALGORITHM = "HS256"
MAX_USER_ID = 2**63 - 1

_jwt = jwt.PyJWT(options={"enforce_minimum_key_length": True})


class InvalidToken(Exception):
    """The access token is expired, forged, malformed or missing a required claim."""


def normalise_password(password: str) -> str:
    """NFC, so the same typed text always produces the same hash."""
    return unicodedata.normalize("NFC", password)


def hash_password(password: str) -> str:
    return _password_hash.hash(normalise_password(password))


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _password_hash.verify(normalise_password(password), hashed_password)
    except UnknownHashError:
        return False


def verify_and_update_password(
    password: str, hashed_password: str
) -> tuple[bool, str | None]:
    """Return (valid, upgraded_hash); the hash is not None when it should be re-stored."""
    try:
        return _password_hash.verify_and_update(
            normalise_password(password), hashed_password
        )
    except UnknownHashError:
        return False, None


# Created at import, not on first use: a hash made lazily would make the first unknown-email
# login after a restart about twice as slow as every later one.
_DUMMY_HASH = hash_password("a password nobody has")


def dummy_verify(password: str) -> None:
    """Spend the same time as a real check, so an unknown email is not faster than a wrong password."""
    verify_password(password, _DUMMY_HASH)


def create_access_token(
    user_id: int, *, secret: str, expires_in: timedelta, now: datetime | None = None
) -> str:
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or not 0 < user_id <= MAX_USER_ID
    ):
        raise ValueError("Invalid user ID")
    if expires_in <= timedelta(0):
        raise ValueError("Token lifetime must be positive")

    issued_at = now if now is not None else datetime.now(UTC)
    if issued_at.tzinfo is None:
        raise ValueError("Issued-at datetime must be timezone-aware")
    issued_at = issued_at.astimezone(UTC)

    payload = {"sub": str(user_id), "iat": issued_at, "exp": issued_at + expires_in}
    return _jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> int:
    """Return the user id in a valid token, or raise InvalidToken."""
    try:
        payload = _jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.InvalidTokenError as error:
        raise InvalidToken from error

    subject = payload["sub"]
    if not (
        isinstance(subject, str)
        and subject.isascii()
        and subject.isdigit()
        and subject == str(int(subject))
        and 0 < int(subject) <= MAX_USER_ID
    ):
        raise InvalidToken

    return int(subject)
