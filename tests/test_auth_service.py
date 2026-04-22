from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import jwt
import pytest

from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_register_user_creates_hashed_user() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    created_user = SimpleNamespace(id=1, email="new@example.com", full_name="New User")

    service.user_repository = SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        create_user=AsyncMock(return_value=created_user),
    )

    payload = SimpleNamespace(
        email="new@example.com",
        full_name="New User",
        password="password123",
    )
    result = await service.register_user(payload)

    assert result is created_user
    service.user_repository.get_by_email.assert_awaited_once_with("new@example.com")
    create_call = service.user_repository.create_user.await_args.kwargs
    assert create_call["email"] == "new@example.com"
    assert create_call["full_name"] == "New User"
    assert create_call["password_hash"] != "password123"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_user_rejects_duplicate_email() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    service.user_repository = SimpleNamespace(
        get_by_email=AsyncMock(return_value=SimpleNamespace(id=1)),
    )

    with pytest.raises(ValueError, match="already exists"):
        await service.register_user(
            SimpleNamespace(
                email="taken@example.com",
                full_name="Taken User",
                password="password123",
            )
        )


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_for_unknown_user() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    service.user_repository = SimpleNamespace(get_by_email=AsyncMock(return_value=None))

    result = await service.authenticate_user("missing@example.com", "password123")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_for_invalid_password() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    user = SimpleNamespace(password_hash="hashed")
    service.user_repository = SimpleNamespace(get_by_email=AsyncMock(return_value=user))

    original_verify = service.authenticate_user.__globals__["verify_password"]
    service.authenticate_user.__globals__["verify_password"] = lambda *_args: False

    try:
        result = await service.authenticate_user("alex@example.com", "bad-password")
    finally:
        service.authenticate_user.__globals__["verify_password"] = original_verify

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_for_valid_password() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    user = SimpleNamespace(password_hash="hashed", email="alex@example.com")
    service.user_repository = SimpleNamespace(get_by_email=AsyncMock(return_value=user))

    original_verify = service.authenticate_user.__globals__["verify_password"]
    service.authenticate_user.__globals__["verify_password"] = lambda *_args: True

    try:
        result = await service.authenticate_user("alex@example.com", "password123")
    finally:
        service.authenticate_user.__globals__["verify_password"] = original_verify

    assert result is user


@pytest.mark.asyncio
async def test_issue_tokens_returns_bearer_pair() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    user = SimpleNamespace(id=42)

    tokens = await service.issue_tokens(user)

    assert tokens.token_type == "bearer"
    assert tokens.access_token
    assert tokens.refresh_token


@pytest.mark.asyncio
async def test_refresh_tokens_blacklists_old_refresh_token() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    user = SimpleNamespace(id=5)
    replacement_tokens = SimpleNamespace(access_token="a", refresh_token="b")

    service.validate_token = AsyncMock(return_value={"sub": "5"})
    service.user_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=user))
    service.blacklist_token = AsyncMock()
    service.issue_tokens = AsyncMock(return_value=replacement_tokens)

    result = await service.refresh_tokens("refresh-token")

    assert result is replacement_tokens
    service.validate_token.assert_awaited_once_with("refresh-token", expected_type="refresh")
    service.user_repository.get_by_id.assert_awaited_once_with(5)
    service.blacklist_token.assert_awaited_once_with("refresh-token")
    service.issue_tokens.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_refresh_tokens_raises_when_user_missing() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)

    service.validate_token = AsyncMock(return_value={"sub": "88"})
    service.user_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=None))

    with pytest.raises(ValueError, match="User not found"):
        await service.refresh_tokens("refresh-token")


@pytest.mark.asyncio
async def test_blacklist_token_stores_ttl_in_redis() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    original_decode = service.blacklist_token.__globals__["decode_token"]
    service.blacklist_token.__globals__["decode_token"] = lambda _token: {
        "jti": "abc-123",
        "exp": int(expires_at.timestamp()),
    }

    try:
        await service.blacklist_token("token-value")
    finally:
        service.blacklist_token.__globals__["decode_token"] = original_decode

    redis.setex.assert_awaited_once()
    key, ttl, marker = redis.setex.await_args.args
    assert key == "blacklist:abc-123"
    assert ttl > 0
    assert marker == "1"


@pytest.mark.asyncio
async def test_is_token_blacklisted_checks_redis_flag() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    redis.exists.return_value = 1
    service = AuthService(session, redis)

    result = await service.is_token_blacklisted("blocked-jti")

    assert result is True


@pytest.mark.asyncio
async def test_validate_token_rejects_invalid_token() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)

    original_decode = service.validate_token.__globals__["decode_token"]
    service.validate_token.__globals__["decode_token"] = lambda _token: (_ for _ in ()).throw(
        jwt.PyJWTError("boom")
    )

    try:
        with pytest.raises(ValueError, match="Invalid token"):
            await service.validate_token("bad-token", expected_type="access")
    finally:
        service.validate_token.__globals__["decode_token"] = original_decode


@pytest.mark.asyncio
async def test_validate_token_rejects_wrong_type() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)

    original_decode = service.validate_token.__globals__["decode_token"]
    service.validate_token.__globals__["decode_token"] = lambda _token: {
        "type": "refresh",
        "jti": "jti-1",
    }

    try:
        with pytest.raises(ValueError, match="Invalid token type"):
            await service.validate_token("token", expected_type="access")
    finally:
        service.validate_token.__globals__["decode_token"] = original_decode


@pytest.mark.asyncio
async def test_validate_token_rejects_blacklisted_token() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    service.is_token_blacklisted = AsyncMock(return_value=True)

    original_decode = service.validate_token.__globals__["decode_token"]
    service.validate_token.__globals__["decode_token"] = lambda _token: {
        "type": "access",
        "jti": "jti-1",
    }

    try:
        with pytest.raises(ValueError, match="revoked"):
            await service.validate_token("token", expected_type="access")
    finally:
        service.validate_token.__globals__["decode_token"] = original_decode


@pytest.mark.asyncio
async def test_validate_token_returns_payload_when_valid() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = AuthService(session, redis)
    service.is_token_blacklisted = AsyncMock(return_value=False)
    payload = {"type": "access", "jti": "jti-1", "sub": "7"}

    original_decode = service.validate_token.__globals__["decode_token"]
    service.validate_token.__globals__["decode_token"] = lambda _token: payload

    try:
        result = await service.validate_token("token", expected_type="access")
    finally:
        service.validate_token.__globals__["decode_token"] = original_decode

    assert result == payload
