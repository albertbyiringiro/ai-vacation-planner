from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trip, User
from app.schemas.trips import TripCreate


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
    """The Trip if it exists AND belongs to owner_id; None for a missing and a foreign Trip alike.

    Every route that takes a trip id goes through here (OWASP API1:2023, object-level authorization),
    so there is one place that decides ownership."""
    return db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == owner_id))
