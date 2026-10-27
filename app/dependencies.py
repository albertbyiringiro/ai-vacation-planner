from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import InvalidToken, decode_access_token
from app.settings import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)
DBSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    db: DBSession,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise _unauthorized("Authentication required")

    try:
        user_id = decode_access_token(
            credentials.credentials, secret=settings.jwt_secret.get_secret_value()
        )
    except InvalidToken as error:
        raise _unauthorized("Invalid or expired access token") from error

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid or expired access token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
