from fastapi import APIRouter, HTTPException

from app.dependencies import DBSession
from app.models import User
from app.schemas.users import UserCreate, UserRead
from app.services.users import EmailAlreadyRegistered, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserRead)
def register(data: UserCreate, db: DBSession) -> User:
    try:
        return register_user(db, data)
    except EmailAlreadyRegistered as error:
        raise HTTPException(
            status_code=409, detail="Email already registered"
        ) from error
