from sqlalchemy.orm import Session

from core.models import Entity


def create_test_entity(db_session: Session, name="Test Entity"):
    entity = Entity(name=name)
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    return entity
