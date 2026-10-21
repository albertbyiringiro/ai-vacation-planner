from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]

    trips: Mapped[list["Trip"]] = relationship(back_populates="owner")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("days > 0", name="days_positive"),
        CheckConstraint("budget >= 0", name="budget_not_negative"),
        CheckConstraint("length(destination) > 0", name="destination_not_empty"),
        CheckConstraint("length(trip_style) > 0", name="trip_style_not_empty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    destination: Mapped[str]
    days: Mapped[int]
    budget: Mapped[int]  # whole US dollars
    trip_style: Mapped[str]

    owner: Mapped[User] = relationship(back_populates="trips")
    itinerary: Mapped["Itinerary | None"] = relationship(
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )


class Itinerary(Base):
    __tablename__ = "itineraries"
    __table_args__ = (UniqueConstraint("trip_id"),)  # one current Itinerary per Trip

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))

    trip: Mapped[Trip] = relationship(back_populates="itinerary")
    days: Mapped[list["Day"]] = relationship(
        back_populates="itinerary",
        order_by="Day.number",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Day(Base):
    __tablename__ = "days"
    __table_args__ = (
        CheckConstraint("number >= 1", name="number_starts_at_one"),
        UniqueConstraint("itinerary_id", "number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    itinerary_id: Mapped[int] = mapped_column(
        ForeignKey("itineraries.id", ondelete="CASCADE")
    )
    number: Mapped[int]

    itinerary: Mapped[Itinerary] = relationship(back_populates="days")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="day",
        order_by="Activity.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="name_not_empty"),
        CheckConstraint("position >= 1", name="position_starts_at_one"),
        UniqueConstraint("day_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("days.id", ondelete="CASCADE"))
    name: Mapped[str]
    position: Mapped[int]

    day: Mapped[Day] = relationship(back_populates="activities")
