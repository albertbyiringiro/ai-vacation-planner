from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.models import Day, Itinerary, Trip, User
from app.schemas.trips import TripCreate, TripUpdate


def create_trip(db: Session, owner: User, data: TripCreate) -> Trip:
    trip = Trip(owner_id=owner.id, **data.model_dump())
    db.add(trip)
    db.commit()
    return trip


def owner_trips_query(owner_id: int, *, limit: int, offset: int):
    return (
        select(Trip)
        .where(Trip.owner_id == owner_id)
        .order_by(Trip.id)
        .limit(limit)
        .offset(offset)
    )


def list_trips(db: Session, owner_id: int, *, limit: int, offset: int) -> list[Trip]:
    return list(db.scalars(owner_trips_query(owner_id, limit=limit, offset=offset)))


def get_owned_trip(db: Session, owner_id: int, trip_id: int) -> Trip | None:
    """The Trip if it exists AND belongs to owner_id; None for a missing and a foreign Trip alike."""
    return db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == owner_id))


class ItineraryOutgrowsTrip(Exception):
    """The Trip would end up shorter than its Itinerary."""

    def __init__(self, last_day: int) -> None:
        super().__init__(f"The itinerary already uses day {last_day}")
        self.last_day = last_day


class TripVanished(Exception):
    """The Trip was deleted (by another request) between the lookup and the update."""


def update_trip(db: Session, trip: Trip, data: TripUpdate) -> Trip:
    last_day = db.scalar(
        select(func.max(Day.number))
        .join(Itinerary, Day.itinerary_id == Itinerary.id)
        .where(Itinerary.trip_id == trip.id)
    )
    if last_day is not None and data.days < last_day:
        raise ItineraryOutgrowsTrip(last_day)
    for field, value in data.model_dump().items():
        setattr(trip, field, value)
    try:
        db.commit()
    except StaleDataError as error:
        # the UPDATE matched no row: another request deleted the Trip after our lookup
        db.rollback()
        raise TripVanished from error
    return trip


def delete_trip(db: Session, trip: Trip) -> None:
    """Deleting the Trip deletes its Itinerary, Days and Activities"""
    db.delete(trip)
    db.commit()
