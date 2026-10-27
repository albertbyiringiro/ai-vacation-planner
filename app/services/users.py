from sqlite3 import IntegrityError

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.users import UserCreate
from app.security import hash_password


class EmailAlreadyRegistered(Exception):
    """Raised when the email already belongs to a user"""


def register_user(db: Session, data: UserCreate) -> User:
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()

        if "UNIQUE constraint failed: users.email" not in str(error.orig):
            raise

        raise EmailAlreadyRegistered(data.email) from error

    return user
