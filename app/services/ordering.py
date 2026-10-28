from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Activity, Day, Itinerary, Trip


class OrderingNotFound(Exception):
    """Resource does not exist or is not owned by this user."""


class InvalidOrder(ValueError):
    """Invalid position or sequence of IDs."""


def _validate_order[T: (Day, Activity)](
    items: Sequence[T],
    requested_ids: Sequence[int],
) -> None:
    existing_ids = [item.id for item in items]

    if (
        len(requested_ids) != len(existing_ids)
        or len(set(requested_ids)) != len(requested_ids)
        or set(requested_ids) != set(existing_ids)
    ):
        raise InvalidOrder("Provide every existing ID exactly once.")


def _validate_insert_position(
    position: int | None,
    count: int,
) -> int:
    if position is None:
        return count + 1

    if not 1 <= position <= count + 1:
        raise InvalidOrder(f"Position must be between 1 and {count + 1}.")

    return position


def _assign_positions[T: (Day, Activity)](
    db: Session,
    *,
    items: Sequence[T],
    ordered_ids: Sequence[int],
    field: str,
) -> None:
    """
    Assign consecutive positions using two phases.

    This helper does not commit. The calling operation
    owns the transaction.
    """
    _validate_order(items, ordered_ids)

    if not items:
        return

    by_id = {item.id: item for item in items}

    offset = max(getattr(item, field) for item in items)

    # Phase 1: move every record above the occupied range.
    for index, item in enumerate(items, start=1):
        setattr(item, field, offset + index)

    db.flush()

    # Phase 2: assign final consecutive positions.
    for index, item_id in enumerate(ordered_ids, start=1):
        setattr(by_id[item_id], field, index)

    db.flush()


def _lock_itinerary(
    db: Session,
    *,
    itinerary_id: int,
    user_id: int,
) -> None:
    """
    Acquire a SQLite write reservation on an owned itinerary
    before reading its days.
    """
    result = db.execute(
        update(Itinerary)
        .where(
            Itinerary.id == itinerary_id,
            Itinerary.trip.has(Trip.owner_id == user_id),
        )
        .values(id=Itinerary.id)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        raise OrderingNotFound("Itinerary not found")


def _lock_day(
    db: Session,
    *,
    day_id: int,
    user_id: int,
) -> None:
    """Acquire a SQLite write reservation on an owned day."""
    result = db.execute(
        update(Day)
        .where(
            Day.id == day_id,
            Day.itinerary.has(Itinerary.trip.has(Trip.owner_id == user_id)),
        )
        .values(id=Day.id)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        raise OrderingNotFound("Day not found")


def _get_days(
    db: Session,
    itinerary_id: int,
) -> list[Day]:
    return list(
        db.scalars(
            select(Day)
            .where(Day.itinerary_id == itinerary_id)
            .order_by(Day.number, Day.id)
        )
    )


def _get_activities(
    db: Session,
    day_id: int,
) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.day_id == day_id)
            .order_by(Activity.position, Activity.id)
        )
    )


def _day_result(days: Sequence[Day]) -> list[dict]:
    return [{"id": day.id, "number": day.number} for day in days]


def _activity_result(
    activities: Sequence[Activity],
) -> list[dict]:
    return [
        {
            "id": activity.id,
            "name": activity.name,
            "position": activity.position,
        }
        for activity in activities
    ]


# -------------------------------------------------------
# DAYS
# -------------------------------------------------------


def reorder_days(
    db: Session,
    *,
    itinerary_id: int,
    user_id: int,
    day_ids: Sequence[int],
) -> list[dict]:
    try:
        _lock_itinerary(db, itinerary_id=itinerary_id, user_id=user_id)

        days = _get_days(db, itinerary_id)
        _validate_order(days, day_ids)

        _assign_positions(
            db,
            items=days,
            ordered_ids=day_ids,
            field="number",
        )

        by_id = {day.id: day for day in days}
        result = _day_result([by_id[id_] for id_ in day_ids])

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def insert_day(
    db: Session,
    *,
    itinerary_id: int,
    user_id: int,
    position: int | None = None,
) -> list[dict]:
    try:
        _lock_itinerary(db, itinerary_id=itinerary_id, user_id=user_id)

        days = _get_days(db, itinerary_id)
        insert_at = _validate_insert_position(position, len(days))

        max_number = max(
            (day.number for day in days),
            default=0,
        )

        new_day = Day(
            itinerary_id=itinerary_id,
            number=max_number + 1,
        )

        db.add(new_day)
        db.flush()

        ordered_ids = [day.id for day in days]
        ordered_ids.insert(insert_at - 1, new_day.id)

        _assign_positions(
            db,
            items=[*days, new_day],
            ordered_ids=ordered_ids,
            field="number",
        )

        all_days = {day.id: day for day in [*days, new_day]}

        result = _day_result([all_days[id_] for id_ in ordered_ids])

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def delete_day(
    db: Session,
    *,
    itinerary_id: int,
    day_id: int,
    user_id: int,
) -> list[dict]:
    try:
        _lock_itinerary(db, itinerary_id=itinerary_id, user_id=user_id)

        days = _get_days(db, itinerary_id)
        target = next(
            (day for day in days if day.id == day_id),
            None,
        )

        if target is None:
            raise OrderingNotFound("Day not found")

        remaining = [day for day in days if day.id != day_id]

        db.delete(target)
        db.flush()

        ordered_ids = [day.id for day in remaining]

        _assign_positions(
            db,
            items=remaining,
            ordered_ids=ordered_ids,
            field="number",
        )

        result = _day_result(remaining)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


# -------------------------------------------------------
# ACTIVITIES
# -------------------------------------------------------


def reorder_activities(
    db: Session,
    *,
    day_id: int,
    user_id: int,
    activity_ids: Sequence[int],
) -> list[dict]:
    try:
        _lock_day(db, day_id=day_id, user_id=user_id)

        activities = _get_activities(db, day_id)
        _validate_order(activities, activity_ids)

        _assign_positions(
            db,
            items=activities,
            ordered_ids=activity_ids,
            field="position",
        )

        by_id = {activity.id: activity for activity in activities}

        result = _activity_result([by_id[id_] for id_ in activity_ids])

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def insert_activity(
    db: Session,
    *,
    day_id: int,
    user_id: int,
    name: str,
    position: int | None = None,
) -> list[dict]:
    try:
        _lock_day(db, day_id=day_id, user_id=user_id)

        activities = _get_activities(db, day_id)
        insert_at = _validate_insert_position(position, len(activities))

        clean_name = name.strip()

        if not clean_name:
            raise InvalidOrder("Activity name cannot be blank.")

        max_position = max(
            (activity.position for activity in activities),
            default=0,
        )

        new_activity = Activity(
            day_id=day_id,
            name=clean_name,
            position=max_position + 1,
        )

        db.add(new_activity)
        db.flush()

        ordered_ids = [activity.id for activity in activities]
        ordered_ids.insert(insert_at - 1, new_activity.id)

        _assign_positions(
            db,
            items=[*activities, new_activity],
            ordered_ids=ordered_ids,
            field="position",
        )

        all_activities = {
            activity.id: activity for activity in [*activities, new_activity]
        }

        result = _activity_result([all_activities[id_] for id_ in ordered_ids])

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise


def delete_activity(
    db: Session,
    *,
    day_id: int,
    activity_id: int,
    user_id: int,
) -> list[dict]:
    try:
        _lock_day(db, day_id=day_id, user_id=user_id)

        activities = _get_activities(db, day_id)

        target = next(
            (activity for activity in activities if activity.id == activity_id),
            None,
        )

        if target is None:
            raise OrderingNotFound("Activity not found")

        remaining = [activity for activity in activities if activity.id != activity_id]

        db.delete(target)
        db.flush()

        ordered_ids = [activity.id for activity in remaining]

        _assign_positions(
            db,
            items=remaining,
            ordered_ids=ordered_ids,
            field="position",
        )

        result = _activity_result(remaining)

        db.commit()
        return result

    except Exception:
        db.rollback()
        raise
