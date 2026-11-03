from pydantic import BaseModel, ConfigDict, Field

MAX_TRIP_DAYS = 60
MAX_BUDGET = 1_000_000


class TripCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    destination: str = Field(min_length=1, max_length=100)
    days: int = Field(ge=1, le=MAX_TRIP_DAYS)
    budget: int = Field(ge=0, le=MAX_BUDGET)
    trip_style: str = Field(min_length=1, max_length=50)


class TripUpdate(TripCreate):
    """PUT replaces the whole Trip, so every field is required, exactly as on create."""


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    destination: str
    days: int
    budget: int
    trip_style: str


class TripCreated(TripRead):
    message: str = "Trip created successfully"
