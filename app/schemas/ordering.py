from pydantic import BaseModel, ConfigDict, Field


class ReorderDaysRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_ids: list[int] = Field(min_length=1)


class ReorderActivitiesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_ids: list[int] = Field(min_length=1)


class DayCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: int | None = Field(default=None, ge=1)


class ActivityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    position: int | None = Field(default=None, ge=1)


class DayOrderRead(BaseModel):
    id: int
    number: int


class ActivityOrderRead(BaseModel):
    id: int
    name: str
    position: int


class DayOrderResponse(BaseModel):
    days: list[DayOrderRead]


class ActivityOrderResponse(BaseModel):
    activities: list[ActivityOrderRead]
