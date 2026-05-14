from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_scheme = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def require_api_key(api_key: str = Security(api_key_scheme)) -> str:
    if not api_key or api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
