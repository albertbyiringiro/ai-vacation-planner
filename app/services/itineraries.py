from collections.abc import Callable

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import Activity, Day, Itinerary, Trip
from app.schemas.itineraries import DayData, ItineraryCreate, ItineraryRead


class DayBeyondTrip(Exception):
    """A Day number is larger than the number of days the Trip lasts."""

    def __init__(self, day: int, trip_days: int) -> None:
        super().__init__(f"Cannot plan day {day}: the trip lasts {trip_days} days")


class ItineraryExists(Exception):
    """The Trip already has its one Itinerary."""


class ItineraryBusy(Exception):
    """Another request holds the database's write lock: nothing was changed."""


class TripVanished(Exception):
    """The Trip was deleted (by another request) between the lookup and the insert."""


def check_days_fit(days: list[DayData], trip: Trip) -> None:
    for day in days:
        if day.day > trip.days:
            raise DayBeyondTrip(day.day, trip.days)


def new_itinerary(trip_id: int, days: list[DayData]) -> Itinerary:
    itinerary = Itinerary(trip_id=trip_id)
    for day in days:
        itinerary.days.append(
            Day(
                number=day.day,
                activities=[
                    Activity(name=name, position=position)
                    for position, name in enumerate(day.activities, start=1)
                ],
            )
        )
    return itinerary


def commit_new_itinerary(db: Session) -> None:
    """Commit, turning the database's refusals into our own errors and undoing the transaction on
    any failure."""
    translate_database_errors(db, db.commit)


def translate_database_errors(db: Session, action: Callable[[], None]) -> None:
    """Run a step that writes (a flush or a commit) with the refusals mapped to our errors."""
    try:
        action()
    except IntegrityError as error:
        db.rollback()
        message = str(error.orig)
        if "UNIQUE constraint failed: itineraries.trip_id" in message:
            raise ItineraryExists from error
        if "FOREIGN KEY constraint failed" in message:
            raise TripVanished from error
        raise
    except OperationalError as error:
        db.rollback()
        if "database is locked" in str(error.orig):
            raise ItineraryBusy from error
        raise
    except Exception:
        db.rollback()
        raise


def create_itinerary(db: Session, trip: Trip, data: ItineraryCreate) -> Itinerary:
    days = data.days or []
    check_days_fit(days, trip)
    itinerary = new_itinerary(trip.id, days)
    db.add(itinerary)
    commit_new_itinerary(db)
    db.expire_all()
    return itinerary


def replace_itinerary(db: Session, trip: Trip, days: list[DayData]) -> Itinerary:
    """Replace the Trip's Itinerary (if it has one) with a new one, in a single transaction.

    The old one is deleted and that delete is flushed before the new one is inserted, or the unique
    trip_id constraint would fire (the database removes its days and activities with it). Nothing
    is permanent until the one commit: if anything fails, the old Itinerary is still there."""
    check_days_fit(days, trip)
    if trip.itinerary is not None:
        db.delete(trip.itinerary)
        translate_database_errors(db, db.flush)
    itinerary = new_itinerary(trip.id, days)
    db.add(itinerary)
    commit_new_itinerary(db)
    db.expire_all()
    return itinerary


def to_read_model(trip_id: int, itinerary: Itinerary) -> ItineraryRead:
    """Days in day order (the relationship sorts them), activities in position order."""
    return ItineraryRead(
        trip_id=trip_id,
        itinerary=[
            DayData(day=day.number, activities=[a.name for a in day.activities])
            for day in itinerary.days
        ],
    )
