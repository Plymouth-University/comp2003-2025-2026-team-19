import datetime
import uuid

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AttributeMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    datatype: Mapped[str] = mapped_column(String(50), nullable=False, default="string")


class Entity(Base):
    __tablename__ = "Entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="Generic")
    image_url: Mapped[str] = mapped_column(String(255), nullable=True)

    attributes: Mapped[list["EntityAttribute"]] = relationship(
        "EntityAttribute", back_populates="parent", cascade="all, delete-orphan"
    )
    positions: Mapped[list["GPSTelemetry"]] = relationship(
        "GPSTelemetry", back_populates="entity", cascade="all, delete-orphan"
    )
    current_route: Mapped["EntityOnRoute"] = relationship(
        "EntityOnRoute", back_populates="entity", uselist=False, viewonly=True
    )


class GPSTelemetry(Base):
    __tablename__ = "GPSTelemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Entity.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        server_default=func.now(),
    )
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )

    entity: Mapped["Entity"] = relationship(back_populates="positions")

    __table_args__ = (Index("ix_entity_timestamp", "entity_id", "timestamp"),)


class EntityAttribute(AttributeMixin, Base):
    __tablename__ = "EntityAttribute"

    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Entity.id", ondelete="CASCADE"), nullable=False
    )

    parent: Mapped["Entity"] = relationship(back_populates="attributes")

    __table_args__ = (UniqueConstraint("parent_id", "key"),)


class EntityOnRoute(Base):
    __tablename__ = "EntityOnRoute"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("Entity.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Route.id", ondelete="CASCADE"), nullable=False
    )

    entity: Mapped["Entity"] = relationship("Entity", back_populates="current_route")
    route: Mapped["Route"] = relationship("Route")


class Route(Base):
    __tablename__ = "Route"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        server_default=func.gen_random_uuid(),
    )
    start_location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Location.id", ondelete="CASCADE"), nullable=False
    )
    end_location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Location.id", ondelete="CASCADE"), nullable=False
    )
    inverse_route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Route.id", ondelete="CASCADE"), nullable=True
    )

    attributes: Mapped[list["RouteAttribute"]] = relationship(
        "RouteAttribute", back_populates="parent", cascade="all, delete-orphan"
    )
    points: Mapped[list["Point"]] = relationship(
        "Point",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="Point.sequence",
    )
    stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
    )
    start_location: Mapped["Location"] = relationship(
        "Location", foreign_keys=[start_location_id]
    )
    end_location: Mapped["Location"] = relationship(
        "Location", foreign_keys=[end_location_id]
    )
    inverse_route: Mapped["Route"] = relationship("Route", remote_side=[id])


class RouteAttribute(AttributeMixin, Base):
    __tablename__ = "RouteAttribute"

    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Route.id", ondelete="CASCADE"), nullable=False
    )

    parent: Mapped["Route"] = relationship(back_populates="attributes")

    __table_args__ = (UniqueConstraint("parent_id", "key"),)


class Point(Base):
    __tablename__ = "Point"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Route.id", ondelete="CASCADE"), nullable=False
    )
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    route: Mapped["Route"] = relationship(back_populates="points")


class Location(Base):
    __tablename__ = "Location"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )

    attributes: Mapped[list["LocationAttribute"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )


class LocationAttribute(AttributeMixin, Base):
    __tablename__ = "LocationAttribute"

    parent_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Location.id", ondelete="CASCADE"), nullable=False
    )

    parent: Mapped["Location"] = relationship(back_populates="attributes")

    __table_args__ = (UniqueConstraint("parent_id", "key"),)


class RouteStop(Base):
    __tablename__ = "RouteStop"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Route.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Location.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    route: Mapped["Route"] = relationship(back_populates="stops")
    location: Mapped["Location"] = relationship()


class APIKey(Base):
    __tablename__ = "APIKey"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
        server_default=func.now(),
    )
    allowed_entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("Entity.id"), nullable=True
    )
    allowed_entity: Mapped["Entity"] = relationship("Entity")
