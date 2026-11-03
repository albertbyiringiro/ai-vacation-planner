from sqlite3 import IntegrityError

from app.dependencies import DBSession
from app.models import Activity, Day, Itinerary, Trip
from app.schemas.itineraries import DayData, ItineraryCreate, ItineraryRead


class DayBeyondTrip(Exception):
    """A Day number is larger than the number of days the Trip lasts"""

    def __init__(self, day: int, trip_days: int) -> None:
        super().__init__(f"Cannot plan day {day}: the trip lasts {trip_days} days")


class ItineraryExists(Exception):
    """The Trip already has its own Itinerary"""


class TripVanished(Exception):
    """The Trip was deleted (by another request) between the lookup"""


def create_itinerary(db: DBSession, trip: Trip, data: ItineraryCreate) -> ItineraryRead:
    for day in data.days:
        if day > trip.days:
            raise DayBeyondTrip(day.day, trip.days)

    itinerary = Itinerary(trip_id=trip.id)
    for day in data.days:
        itinerary.days.append(
            Day(
                number=day.day,
                activities=[
                    Activity(name=name, position=position)
                    for position, name in enumerate(day.activities, start=1)
                ],
            )
        )

    db.add(itinerary)

    try:
        db.commit()
    except IntegrityError as error:
        # UNIQUE(trip_id): the database, not a check-then-insert, decides who wins a race.
        db.rollback()
        message = str(error.orig)
        if "UNIQUE constraint failed: itineraries.trip_id" in message:
            raise ItineraryExists from error
        if "FOREIGN KEY constraint failed" in message:
            raise TripVanished from error
        raise
    # Build the response from what the database returns, exactly as GET does: after a commit the
    # in-memory collections still hold the order the client sent (days 3 then 1), not day order.
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
