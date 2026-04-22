from datetime import UTC, datetime

import jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenPair, UserCreate


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.redis = redis
        self.user_repository = UserRepository(session)

    async def register_user(self, payload: UserCreate) -> User:
        existing_user = await self.user_repository.get_by_email(payload.email)
        if existing_user is not None:
            raise ValueError("User with this email already exists.")

        user = await self.user_repository.create_user(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        await self.session.commit()
        return user

    async def authenticate_user(self, email: str, password: str) -> User | None:
        user = await self.user_repository.get_by_email(email)
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def issue_tokens(self, user: User) -> TokenPair:
        access_token, access_expires_at, _ = create_access_token(str(user.id))
        refresh_token, refresh_expires_at, _ = create_refresh_token(str(user.id))
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenPair:
        payload = await self.validate_token(refresh_token, expected_type="refresh")
        user = await self.user_repository.get_by_id(int(payload["sub"]))
        if user is None:
            raise ValueError("User not found.")

        await self.blacklist_token(refresh_token)
        return await self.issue_tokens(user)

    async def blacklist_token(self, token: str) -> None:
        payload = decode_token(token)
        jti = payload["jti"]
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)
        ttl_seconds = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
        if ttl_seconds > 0:
            await self.redis.setex(f"blacklist:{jti}", ttl_seconds, "1")

    async def is_token_blacklisted(self, jti: str) -> bool:
        return await self.redis.exists(f"blacklist:{jti}") == 1

    async def validate_token(self, token: str, *, expected_type: str) -> dict:
        try:
            payload = decode_token(token)
        except jwt.PyJWTError as exc:
            raise ValueError("Invalid token.") from exc

        if payload.get("type") != expected_type:
            raise ValueError("Invalid token type.")

        if await self.is_token_blacklisted(payload["jti"]):
            raise ValueError("Token has been revoked.")

        return payload
