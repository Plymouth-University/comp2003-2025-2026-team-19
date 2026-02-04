from uuid import UUID

from pydantic import Field, computed_field

from .base import BaseSchema


class EntityAttribute(BaseSchema):
    key: str
    value: str
    datatype: str


class EntityBase(BaseSchema):
    uuid: UUID
    name: str
    type: str


class ReadEntity(EntityBase):
    description: str | None = None
    image_url: str | None = None

    attributes: list[EntityAttribute] = []

    current_route: ReadEntityOnRoute | None = Field(None, exclude=True)

    @computed_field
    @property
    def route(self) -> RouteBase | None:
        return self.current_route.route if self.current_route else None


class RouteBase(BaseSchema):
    uuid: UUID


class ReadEntityOnRoute(BaseSchema):
    route: RouteBase
