from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Activity, Day, Itinerary, Trip, User

engine = get_engine()


with Session(engine) as session:
    ada = User(email="ada@example.com", hashed_password="not-a-real-hash")
    trip = Trip(
        owner=ada,
        destination="Paris",
        days=2,
        budget=1500,
        trip_style="budget",
    )
    itinerary = Itinerary(trip=trip)

    day1 = Day(number=1)
    day1.activities = [
        Activity(name="Eiffel Tower", position=1),
        Activity(name="Seine River walk", position=2),
    ]
    day2 = Day(number=2)
    day2.activities = [Activity(name="Louvre Museum", position=1)]
    itinerary.days = [day1, day2]

    session.add_all([ada, trip, itinerary])
    session.commit()
    trip_id = trip.id

with Session(engine) as session:
    trip = session.get(Trip, trip_id)
    print(f"{trip.owner.email}: {trip.destination}, {trip.days} days, ${trip.budget}")
    for day in trip.itinerary.days:
        print(f" Day {day.number}: {', '.join(a.name for a in day.activities)}")
