import json

from redis.asyncio import Redis

from app.config import get_settings
from app.schemas.task import TaskRead

settings = get_settings()


class TaskCacheService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def build_owner_tasks_key(owner_id: int) -> str:
        return f"tasks:owner:{owner_id}"

    async def get_tasks_for_owner(self, owner_id: int) -> list[TaskRead] | None:
        cached = await self.redis.get(self.build_owner_tasks_key(owner_id))
        if not cached:
            return None
        payload = json.loads(cached)
        return [TaskRead.model_validate(item) for item in payload]

    async def set_tasks_for_owner(self, owner_id: int, tasks: list[TaskRead]) -> None:
        payload = [task.model_dump(mode="json") for task in tasks]
        await self.redis.setex(
            self.build_owner_tasks_key(owner_id),
            settings.task_cache_ttl_seconds,
            json.dumps(payload),
        )

    async def invalidate_owner_tasks(self, owner_id: int) -> None:
        await self.redis.delete(self.build_owner_tasks_key(owner_id))
