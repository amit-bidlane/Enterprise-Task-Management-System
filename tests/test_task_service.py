from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.task import Task
from app.schemas.task import TaskRead
from app.services.task import TaskService
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_create_task_commits_invalidates_cache_and_dispatches_notification() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = TaskService(session, redis)

    created_task = Task(
        id=1,
        title="Prepare launch brief",
        description="Coordinate with stakeholders",
        status="pending",
        owner_id=7,
    )
    owner = SimpleNamespace(email="owner@example.com", full_name="Casey Owner")

    service.task_repository = SimpleNamespace(add=AsyncMock(return_value=created_task))
    service.user_repository = SimpleNamespace(get_by_id=AsyncMock(return_value=owner))
    service.cache_service = SimpleNamespace(invalidate_owner_tasks=AsyncMock())

    delay_mock = Mock()
    original_delay = service.create_task.__globals__["send_task_assignment_email"].delay
    service.create_task.__globals__["send_task_assignment_email"].delay = delay_mock

    try:
        result = await service.create_task(
            title="Prepare launch brief",
            description="Coordinate with stakeholders",
            status="pending",
            owner_id=7,
        )
    finally:
        service.create_task.__globals__["send_task_assignment_email"].delay = original_delay

    assert result is created_task
    service.task_repository.add.assert_awaited_once()
    session.commit.assert_awaited_once()
    service.cache_service.invalidate_owner_tasks.assert_awaited_once_with(7)
    service.user_repository.get_by_id.assert_awaited_once_with(7)
    delay_mock.assert_called_once_with(
        recipient_email="owner@example.com",
        recipient_name="Casey Owner",
        task_title="Prepare launch brief",
    )


@pytest.mark.asyncio
async def test_list_tasks_for_owner_uses_cache_when_available() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = TaskService(session, redis)

    cached_tasks = [
        TaskRead(
            id=1,
            title="Cached task",
            description=None,
            status="completed",
            owner_id=3,
            created_at="2026-04-22T00:00:00Z",
            updated_at="2026-04-22T00:00:00Z",
        )
    ]

    service.cache_service = SimpleNamespace(
        get_tasks_for_owner=AsyncMock(return_value=cached_tasks),
        set_tasks_for_owner=AsyncMock(),
    )
    service.task_repository = SimpleNamespace(get_by_owner=AsyncMock())

    result = await service.list_tasks_for_owner(3)

    assert result == cached_tasks
    service.cache_service.get_tasks_for_owner.assert_awaited_once_with(3)
    service.task_repository.get_by_owner.assert_not_called()
    service.cache_service.set_tasks_for_owner.assert_not_called()


@pytest.mark.asyncio
async def test_list_tasks_for_owner_populates_cache_on_miss() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = TaskService(session, redis)

    db_tasks = [
        Task(
            id=4,
            title="Draft report",
            description="Share with leadership",
            status="pending",
            owner_id=9,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    service.cache_service = SimpleNamespace(
        get_tasks_for_owner=AsyncMock(return_value=None),
        set_tasks_for_owner=AsyncMock(),
    )
    service.task_repository = SimpleNamespace(get_by_owner=AsyncMock(return_value=db_tasks))

    result = await service.list_tasks_for_owner(9)

    assert len(result) == 1
    assert result[0].title == "Draft report"
    service.cache_service.get_tasks_for_owner.assert_awaited_once_with(9)
    service.task_repository.get_by_owner.assert_awaited_once_with(9)
    service.cache_service.set_tasks_for_owner.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_task_locks_updates_and_invalidates_cache() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = TaskService(session, redis)

    existing_task = Task(
        id=5,
        title="Old title",
        description="Old description",
        status="pending",
        owner_id=2,
    )
    updated_task = Task(
        id=5,
        title="New title",
        description="Old description",
        status="completed",
        owner_id=2,
    )

    service.task_repository = SimpleNamespace(
        get_for_update_by_owner=AsyncMock(return_value=existing_task),
        update_fields=AsyncMock(return_value=updated_task),
    )
    service.cache_service = SimpleNamespace(invalidate_owner_tasks=AsyncMock())

    result = await service.update_task(
        task_id=5,
        owner_id=2,
        title="New title",
        status="completed",
    )

    assert result is updated_task
    service.task_repository.get_for_update_by_owner.assert_awaited_once_with(5, 2)
    service.task_repository.update_fields.assert_awaited_once_with(
        existing_task,
        {"title": "New title", "status": "completed"},
    )
    session.commit.assert_awaited_once()
    service.cache_service.invalidate_owner_tasks.assert_awaited_once_with(2)


@pytest.mark.asyncio
async def test_update_task_returns_none_when_missing() -> None:
    session = AsyncMock()
    redis = AsyncMock()
    service = TaskService(session, redis)
    service.task_repository = SimpleNamespace(get_for_update_by_owner=AsyncMock(return_value=None))
    service.cache_service = SimpleNamespace(invalidate_owner_tasks=AsyncMock())

    result = await service.update_task(task_id=404, owner_id=1, status="completed")

    assert result is None
    session.commit.assert_not_called()
    service.cache_service.invalidate_owner_tasks.assert_not_called()
