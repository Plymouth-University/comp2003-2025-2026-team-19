from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy import select

from core.database import AsyncSession, get_db_session
from core.models import APIKey

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key: str = Security(api_key_header), db: AsyncSession = Depends(get_db_session)
):
    if api_key is None:
        raise HTTPException(status_code=403, detail="API Key missing")

    prefix = api_key[:12]
    stmt = select(APIKey).where(APIKey.prefix == prefix, APIKey.is_active == True)
    result = await db.execute(stmt)
    potential_keys = result.scalars().all()

    # Hash verification
    for key_obj in potential_keys:
        if pwd_context.verify(api_key, key_obj.key):
            return key_obj

    raise HTTPException(status_code=403, detail="Invalid API Key")
