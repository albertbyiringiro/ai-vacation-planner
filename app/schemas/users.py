import unicodedata
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

PASSWORD_MIN_LENGTH = 15
PASSWORD_MAX_LENGTH = 128
SERVICE_NAME = "vacationplanner"


def normalise_email(email: str) -> str:
    """Canonical form used for storage and lookup."""
    return email.strip().lower()


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, email: str) -> str:
        return normalise_email(email)

    @field_validator("password", mode="before")
    @classmethod
    def normalise_unicode(cls, password: Any) -> Any:
        return (
            unicodedata.normalize("NFC", password)
            if isinstance(password, str)
            else password
        )

    @model_validator(mode="after")
    def reject_context_specific_passwords(self) -> "UserCreate":
        candidate = "".join(self.password.split()).lower()

        if candidate in {SERVICE_NAME, self.email}:
            raise ValueError("Password is too easy to guess")

        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
