from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.database import SQLITE_MAX_INT
from app.schemas.text import reject_hidden_characters
from app.schemas.trips import MAX_TRIP_DAYS

MAX_ACTIVITIES_PER_DAY = 20
Activity = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(reject_hidden_characters),
]


class DayData(BaseModel):
    """One day of an Itinerary in the brief's format: {"day": 1, "activities": ["...", "..."]}."""

    model_config = ConfigDict(extra="forbid")

    day: int = Field(ge=1, le=MAX_TRIP_DAYS)
    activities: list[Activity] = Field(min_length=1, max_length=MAX_ACTIVITIES_PER_DAY)


class ItineraryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: int = Field(ge=1, le=SQLITE_MAX_INT)
    days: list[DayData] | None = Field(
        default=None, min_length=1, max_length=MAX_TRIP_DAYS
    )

    @model_validator(mode="after")
    def day_numbers_are_unique(self) -> "ItineraryCreate":

        if self.days is None:
            return self
        numbers = [day.day for day in self.days]
        if len(numbers) != len(set(numbers)):
            raise ValueError("each day number may appear only once")
        return self


class ItineraryRead(BaseModel):
    """The brief's response shape: {"trip_id": 1, "itinerary": [{"day": 1, "activities": [...]}]}."""

    trip_id: int
    itinerary: list[DayData]


class ItineraryCreated(ItineraryRead):
    message: str = "Itinerary created successfully"
