from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.security import (
    InvalidToken,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_and_update_password,
    verify_password,
)

SECRET = "s" * 32
HOUR = timedelta(hours=1)


def test_password_round_trip_and_unicode_normalisation():
    hashed = hash_password("café password")
    assert verify_password("café password", hashed)
    assert not verify_password("wrong", hashed)


def test_unknown_hash_is_rejected_not_raised():
    assert verify_password("x", "not-a-hash") is False
    assert verify_and_update_password("x", "not-a-hash") == (False, None)


def test_token_round_trip():
    token = create_access_token(7, secret=SECRET, expires_in=HOUR)
    assert decode_access_token(token, secret=SECRET) == 7


@pytest.mark.parametrize("user_id", [0, -1, True, 2**63])
def test_create_token_rejects_bad_user_id(user_id):
    with pytest.raises(ValueError):
        create_access_token(user_id, secret=SECRET, expires_in=HOUR)


def test_create_token_rejects_naive_time_and_non_positive_lifetime():
    with pytest.raises(ValueError):
        create_access_token(1, secret=SECRET, expires_in=HOUR, now=datetime(2030, 1, 1))  # noqa: DTZ001
    with pytest.raises(ValueError):
        create_access_token(1, secret=SECRET, expires_in=timedelta(0))


def test_expired_token_is_rejected():
    past = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(1, secret=SECRET, expires_in=HOUR, now=past)
    with pytest.raises(InvalidToken):
        decode_access_token(token, secret=SECRET)


def test_wrong_secret_and_garbage_are_rejected():
    token = create_access_token(1, secret=SECRET, expires_in=HOUR)
    with pytest.raises(InvalidToken):
        decode_access_token(token, secret="t" * 32)
    with pytest.raises(InvalidToken):
        decode_access_token("garbage", secret=SECRET)


@pytest.mark.parametrize("sub", ["0", "007", "-1", "1.5", " 1", "٣", "1" * 25])
def test_malformed_subject_is_rejected(sub):
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": sub, "iat": now, "exp": now + HOUR}, SECRET, algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, secret=SECRET)


def test_alg_none_token_is_rejected():
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + HOUR}, None, algorithm="none"
    )
    with pytest.raises(InvalidToken):
        decode_access_token(token, secret=SECRET)
