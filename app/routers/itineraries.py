from fastapi import APIRouter, HTTPException

from app.dependencies import (
    CurrentUser,
    DbSession,
    LLMProviderDep,
    TripId,
    trip_not_found,
)
from app.schemas.itineraries import ItineraryCreate, ItineraryCreated, ItineraryRead
from app.services import generation as generation_service
from app.services import itineraries as itineraries_service
from app.services import trips as trips_service

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


@router.post("", status_code=201, response_model=ItineraryCreated)
def create_itinerary(
    data: ItineraryCreate,
    db: DbSession,
    current_user: CurrentUser,
    llm_provider: LLMProviderDep,
) -> ItineraryRead:
    """With `days`: store this manual itinerary (409 if the trip already has one). Without `days`:
    have the model generate one, replacing any existing itinerary."""
    trip = trips_service.get_owned_trip(db, current_user.id, data.trip_id)
    if trip is None:
        raise trip_not_found()
    try:
        if data.days is None:
            llm = llm_provider()
            itinerary = generation_service.generate_itinerary(db, llm, trip)
        else:
            itinerary = itineraries_service.create_itinerary(db, trip, data)
    except itineraries_service.DayBeyondTrip as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except itineraries_service.TripVanished:
        raise trip_not_found() from None
    except generation_service.TripTooLongToGenerate:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Automatic generation supports trips of up to "
                f"{generation_service.MAX_GENERATED_DAYS} days. "
                "Add the itinerary yourself with `days` for a longer trip."
            ),
        ) from None
    except generation_service.GenerationInProgress:
        raise HTTPException(
            status_code=409,
            detail="An itinerary is already being generated for this trip. Please wait for it to finish.",
        ) from None
    except itineraries_service.ItineraryBusy:
        raise HTTPException(
            status_code=409,
            detail="The itinerary is being changed by another request. Please try again.",
        ) from None
    except generation_service.TripChanged:
        raise HTTPException(
            status_code=409,
            detail="The trip changed while the itinerary was being generated. Please try again.",
        ) from None
    except itineraries_service.ItineraryExists:
        raise HTTPException(
            status_code=409, detail="This trip already has an itinerary"
        ) from None
    return itineraries_service.to_read_model(data.trip_id, itinerary)


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
