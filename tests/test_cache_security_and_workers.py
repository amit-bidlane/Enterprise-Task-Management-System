from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.schemas.task import TaskRead
from app.services.cache import TaskCacheService
from app.tasks.notifications import send_task_assignment_email
from app.worker import celery_app


@pytest.mark.asyncio
async def test_task_cache_service_round_trip() -> None:
    redis = AsyncMock()
    service = TaskCacheService(redis)
    task = TaskRead(
        id=1,
        title="Cache me",
        description="Stored in Redis",
        status="pending",
        owner_id=2,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    await service.set_tasks_for_owner(2, [task])

    redis.setex.assert_awaited_once()
    key, ttl, payload = redis.setex.await_args.args
    assert key == "tasks:owner:2"
    assert ttl == 300

    redis.get.return_value = payload
    restored = await service.get_tasks_for_owner(2)

    assert restored is not None
    assert restored[0].title == "Cache me"


@pytest.mark.asyncio
async def test_task_cache_service_handles_cache_miss_and_invalidation() -> None:
    redis = AsyncMock()
    redis.get.return_value = None
    service = TaskCacheService(redis)

    result = await service.get_tasks_for_owner(5)
    await service.invalidate_owner_tasks(5)

    assert result is None
    redis.delete.assert_awaited_once_with("tasks:owner:5")


def test_security_helpers_hash_verify_and_decode_tokens() -> None:
    password = "super-secret"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False

    access_token, _, _ = create_access_token("11")
    refresh_token, _, _ = create_refresh_token("11")

    access_payload = decode_token(access_token)
    refresh_payload = decode_token(refresh_token)

    assert access_payload["sub"] == "11"
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"


def test_settings_build_urls() -> None:
    settings = Settings(
        APP_NAME="Enterprise Task Management System",
        APP_ENV="test",
        APP_PORT=8000,
        POSTGRES_DB="tasks",
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="postgres",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=1,
        JWT_SECRET_KEY="secret",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=15,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        TASK_CACHE_TTL_SECONDS=300,
        CELERY_BROKER_URL="redis://localhost:6379/1",
        FRONTEND_ORIGIN="http://localhost:5173",
    )

    assert settings.database_url.endswith("/tasks")
    assert settings.redis_url == "redis://localhost:6379/1"


def test_notification_task_returns_message() -> None:
    message = send_task_assignment_email.run(
        recipient_email="owner@example.com",
        recipient_name="Owner Name",
        task_title="Quarterly planning",
    )

    assert "owner@example.com" in message
    assert "Quarterly planning" in message


def test_notification_task_raises_for_missing_email() -> None:
    with pytest.raises(RuntimeError, match="Missing recipient email"):
        send_task_assignment_email.run(
            recipient_email="",
            recipient_name="Owner Name",
            task_title="Quarterly planning",
        )


def test_worker_uses_redis_broker_configuration() -> None:
    assert celery_app.conf.broker_url.startswith("redis://")
    assert celery_app.conf.result_backend.startswith("redis://")
