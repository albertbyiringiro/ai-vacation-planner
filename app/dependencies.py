"""Dependencies shared by several routers."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Path
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import SQLITE_MAX_INT, get_db
from app.llm.client import LLMClient
from app.llm.factory import get_llm_client
from app.models import User
from app.security import InvalidToken, decode_access_token
from app.settings import Settings, get_settings

TripId = Annotated[int, Path(ge=1, le=SQLITE_MAX_INT)]
DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: DbSession,
    settings: SettingsDep,
) -> User:
    not_authenticated = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise not_authenticated
    try:
        user_id = decode_access_token(
            token, secret=settings.jwt_secret.get_secret_value()
        )
    except InvalidToken as error:
        raise not_authenticated from error
    user = db.get(User, user_id)
    if user is None:  # a valid token for a user that no longer exists
        raise not_authenticated
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def trip_not_found() -> HTTPException:

    return HTTPException(status_code=404, detail="Trip not found")


def get_llm_provider() -> Callable[[], LLMClient]:
    """A function that returns the application's LLM client when called. It is a function, not the
    client, so a route that only sometimes needs the model (manual itineraries do not) fails for
    a missing API key only when it actually asks for the client. Tests override this dependency."""
    return get_llm_client


LLMProviderDep = Annotated[Callable[[], LLMClient], Depends(get_llm_provider)]
