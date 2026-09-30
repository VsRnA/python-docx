from collections.abc import AsyncIterator
import asyncio
from functools import lru_cache
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession

from document_service.infrastructure.config.settings import get_settings
from document_service.infrastructure.database.session import async_session_factory

bearer = HTTPBearer(auto_error=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> UUID:
    settings = get_settings()
    if settings.app_env != "production" and x_user_id:
        try:
            return UUID(x_user_id)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user identifier") from error

    if credentials is None or not settings.auth_jwks_url:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token is required")
    try:
        signing_key = await asyncio.to_thread(
            _jwks_client(settings.auth_jwks_url).get_signing_key_from_jwt,
            credentials.credentials,
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer,
        )
        subject = str(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token") from error
    return uuid5(NAMESPACE_URL, f"{settings.auth_issuer}|{subject}")
