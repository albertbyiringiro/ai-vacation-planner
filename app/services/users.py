import logging
import sqlite3

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.users import (
    PASSWORD_MAX_LENGTH,
    UserCreate,
    normalise_email,
)
from app.security import (
    dummy_verify,
    hash_password,
    verify_and_update_password,
)

logger = logging.getLogger(__name__)


class EmailAlreadyRegistered(Exception):
    """Raised when an email address is already registered."""


def is_duplicate_email_error(error: IntegrityError) -> bool:
    """
    Detect a SQLite UNIQUE violation on the users.email column.

    Other integrity errors must not be treated as duplicate emails.
    """
    original = error.orig

    if not isinstance(original, sqlite3.IntegrityError):
        return False

    expected_message = (
        f"UNIQUE constraint failed: {User.__table__.name}.{User.email.key}"
    )

    return (
        getattr(original, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
        and str(original) == expected_message
    )


def register_user(
    db: Session,
    data: UserCreate,
) -> User:
    """Create and persist a new user."""

    normalized_email = normalise_email(data.email)

    user = User(
        email=normalized_email,
        hashed_password=hash_password(data.password),
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if is_duplicate_email_error(error):
            raise EmailAlreadyRegistered() from error

        raise
    except SQLAlchemyError:
        db.rollback()
        raise

    db.refresh(user)

    return user


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    """Find a user using the canonical email address."""

    normalized_email = normalise_email(email)

    return db.scalar(select(User).where(User.email == normalized_email))


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """Authenticate a user and optionally upgrade their password hash."""

    if len(password) > PASSWORD_MAX_LENGTH:
        return None

    user = get_user_by_email(db, email)

    if user is None:
        dummy_verify(password)
        return None

    valid, upgraded_hash = verify_and_update_password(
        password,
        user.hashed_password,
    )

    if not valid:
        return None

    if upgraded_hash is not None:
        try:
            user.hashed_password = upgraded_hash
            db.commit()
        except SQLAlchemyError:
            db.rollback()

            # Hash upgrades are best-effort.
            # Do not log passwords or password hashes.
            logger.warning(
                "Password hash upgrade failed for user ID %s",
                user.id,
            )

            # Rollback expires the ORM object's state.
            # Re-fetch it before returning.
            user = db.get(User, user.id)

    return user
