import datetime
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Entity(Base):
    """Represents a generic trackable entity."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "boat", "car"

    image: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)

    locations: Mapped[list["Position"]] = relationship(
        "Position", back_populates="entity", lazy="selectin"
    )

    attributes: Mapped[list["EntityAttribute"]] = relationship(
        "EntityAttribute", back_populates="entity", lazy="joined"
    )


class EntityAttribute(Base):
    """Represents additional attributes for an entity."""

    __tablename__ = "entity_attributes"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )

    # Foreign key to the associated entity
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    value_type: Mapped[str] = mapped_column(
        String(20), default="string", nullable=False
    )

    entity: Mapped["Entity"] = relationship(back_populates="attributes")

    def __repr__(self) -> str:
        return f"Attribute(key={self.key!r}, value={self.value!r}, type={self.value_type!r})"


class Position(Base):
    """Stores a spatial and temporal point for an entity."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )

    # Foreign key to the associated entity
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        index=True,
    )

    # ST_Point represents a single point (longitude, latitude)
    # srid=4326 is the standard World Geodetic System (WGS 84) used by GPS
    geometry = Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=False
    )

    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(tz=datetime.timezone.utc),
        index=True,
        nullable=False,
    )

    # Relationship back to the parent entity
    entity: Mapped["Entity"] = relationship(back_populates="positions")

    def __repr__(self) -> str:
        return f"Position(entity_id={self.entity_id!r}, timestamp={self.timestamp!r})"
