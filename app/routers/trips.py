from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.database import SQLITE_MAX_INT, TripId
from app.dependencies import CurrentUser, DbSession
from app.models import Trip
from app.schemas.trips import TripCreate, TripCreated, TripRead, TripUpdate
from app.services import trips as trips_service

router = APIRouter(prefix="/trips", tags=["trips"])


def trip_not_found() -> HTTPException:
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


@router.put("/{trip_id}", response_model=TripRead)
def update_trip(
    trip_id: TripId, data: TripUpdate, db: DbSession, current_user: CurrentUser
) -> Trip:
    trip = trips_service.get_owned_trip(db, current_user.id, trip_id)
    if trip is None:
        raise trip_not_found()
    try:
        return trips_service.update_trip(db, trip, data)
    except trips_service.ItineraryOutgrowsTrip as error:
        raise HTTPException(
            status_code=409,
            detail=f"{error}; keep at least {error.last_day} days or change the itinerary first",
        ) from error
    except trips_service.TripVanished:
        raise trip_not_found() from None


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip_id: TripId, db: DbSession, current_user: CurrentUser) -> None:
    trip = trips_service.get_owned_trip(db, current_user.id, trip_id)
    if trip is None:
        raise trip_not_found()
    trips_service.delete_trip(db, trip)
