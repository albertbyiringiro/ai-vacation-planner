from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.dependencies import CurrentUser, DBSession, SettingsDep
from app.models import User
from app.schemas.auth import TokenResponse
from app.schemas.users import UserCreate, UserRead
from app.security import create_access_token
from app.services.users import (
    EmailAlreadyRegistered,
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserRead)
def register(data: UserCreate, db: DBSession) -> User:
    try:
        return register_user(db, data)
    except EmailAlreadyRegistered as error:
        raise HTTPException(
            status_code=409, detail="Email already registered"
        ) from error


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
    settings: SettingsDep,
) -> TokenResponse:
    """OAuth2 password flow: the form's `username` field carries the email."""
    user = authenticate_user(db, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        user.id,
        secret=settings.jwt_secret.get_secret_value(),
        expires_in=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return TokenResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
