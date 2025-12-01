import datetime
import uuid
from typing import Optional

from geoalchemy2 import WKBElement
from pydantic import BaseModel, HttpUrl


class AttributeBase(BaseModel):
    key: str
    value: str
    value_type: str


class AttributeCreate(AttributeBase):
    parent_id: uuid.UUID


class AttributeRead(AttributeBase):
    id: int

    class Config:
        orm_mode = True


class PositionBase(BaseModel):
    timestamp: datetime.datetime
    location: WKBElement


class PositionCreate(PositionBase):
    pass


class PositionRead(PositionBase):
    id: int

    class Config:
        orm_mode = True


class EntityBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    image_url: Optional[HttpUrl] = None


class EntityCreate(EntityBase):
    pass


class EntityRead(EntityBase):
    id: uuid.UUID
    attributes: list[AttributeRead] = []
    positions: list[PositionRead] = []

    class Config:
        orm_mode = True
