from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.dependencies import CurrentUser, DbSession
from app.models import Trip
from app.schemas.trips import TripCreate, TripCreated, TripRead
from app.services import trips as trips_service

router = APIRouter(prefix="/trips", tags=["trips"])

# SQLite integers are 64-bit: a larger id or offset would raise OverflowError (a 500).
SQLITE_MAX_INT = 2**63 - 1
TripId = Annotated[int, Path(ge=1, le=SQLITE_MAX_INT)]


def trip_not_found() -> HTTPException:
    # One response for a missing Trip and for someone else's Trip: RFC 9110 15.5.4 allows 404 to
    # hide that a resource exists (ADR 0005).
    return HTTPException(status_code=404, detail="Trip not found")


@router.post("", status_code=201, response_model=TripCreated)
def create_trip(data: TripCreate, db: DbSession, current_user: CurrentUser) -> Trip:
    return trips_service.create_trip(db, current_user, data)


@router.get("", response_model=list[TripRead])
def list_trips(
    db: DbSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=SQLITE_MAX_INT)] = 0,
) -> list[Trip]:
    return trips_service.list_trips(db, current_user.id, limit=limit, offset=offset)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: TripId, db: DbSession, current_user: CurrentUser) -> Trip:
    trip = trips_service.get_owned_trip(db, current_user.id, trip_id)
    if trip is None:
        raise trip_not_found()
    return trip
