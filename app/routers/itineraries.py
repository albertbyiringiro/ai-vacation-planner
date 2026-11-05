from fastapi import APIRouter, HTTPException

from app.dependencies import CurrentUser, DbSession
from app.routers.trips import TripId, trip_not_found
from app.schemas.itineraries import ItineraryCreate, ItineraryCreated, ItineraryRead
from app.services import itineraries as itineraries_service
from app.services import trips as trips_service

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


@router.post("", status_code=201, response_model=ItineraryCreated)
def create_itinerary(
    data: ItineraryCreate, db: DbSession, current_user: CurrentUser
) -> ItineraryRead:
    trip = trips_service.get_owned_trip(db, current_user.id, data.trip_id)
    if trip is None:
        raise trip_not_found()
    try:
        itinerary = itineraries_service.create_itinerary(db, trip, data)
    except itineraries_service.DayBeyondTrip as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except itineraries_service.TripVanished:
        raise trip_not_found() from None
    except itineraries_service.ItineraryExists:
        raise HTTPException(
            status_code=409, detail="This trip already has an itinerary"
        ) from None

    return itineraries_service.to_read_model(trip.id, itinerary)


@router.get("/{trip_id}", response_model=ItineraryRead)
def get_itinerary(
    trip_id: TripId, db: DbSession, current_user: CurrentUser
) -> ItineraryRead:
    trip = trips_service.get_owned_trip(db, current_user.id, trip_id)
    if trip is None:
        raise trip_not_found()
    itinerary = trip.itinerary
    if itinerary is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itineraries_service.to_read_model(trip.id, itinerary)
