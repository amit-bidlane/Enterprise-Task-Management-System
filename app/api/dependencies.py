from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oauth import oauth2_scheme
from app.core.security import decode_token
from app.db.redis import get_redis_client
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.auth import AuthService
from app.services.task import TaskService


async def get_task_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
) -> AsyncGenerator[TaskService, None]:
    yield TaskService(session, redis)


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
) -> AsyncGenerator[AuthService, None]:
    yield AuthService(session, redis)


async def get_current_user_token(token: str = Depends(oauth2_scheme)) -> str:
    return token


async def get_current_user(
    token: str = Depends(get_current_user_token),
    session: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis_client),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except Exception as exc:
        raise credentials_error from exc

    if payload.get("type") != "access":
        raise credentials_error

    if await redis.exists(f"blacklist:{payload['jti']}") == 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if subject is None:
        raise credentials_error

    user_repository = UserRepository(session)
    user = await user_repository.get_by_id(int(subject))
    if user is None:
        raise credentials_error

    return user
