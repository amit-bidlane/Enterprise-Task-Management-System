from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.task import TaskRead
from app.services.cache import TaskCacheService
from app.tasks.notifications import send_task_assignment_email


class TaskService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.redis = redis
        self.task_repository = TaskRepository(session)
        self.user_repository = UserRepository(session)
        self.cache_service = TaskCacheService(redis)

    async def create_task(
        self,
        *,
        title: str,
        owner_id: int,
        description: str | None = None,
        status: str = "pending",
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            status=status,
            owner_id=owner_id,
        )
        created_task = await self.task_repository.add(task)
        await self.session.commit()
        await self.cache_service.invalidate_owner_tasks(owner_id)

        owner = await self.user_repository.get_by_id(owner_id)
        if owner is not None:
            send_task_assignment_email.delay(
                recipient_email=owner.email,
                recipient_name=owner.full_name,
                task_title=created_task.title,
            )

        return created_task

    async def list_tasks_for_owner(self, owner_id: int) -> list[TaskRead]:
        cached_tasks = await self.cache_service.get_tasks_for_owner(owner_id)
        if cached_tasks is not None:
            return cached_tasks

        tasks = await self.task_repository.get_by_owner(owner_id)
        serialized_tasks = [TaskRead.model_validate(task) for task in tasks]
        await self.cache_service.set_tasks_for_owner(owner_id, serialized_tasks)
        return serialized_tasks

    async def update_task(
        self,
        *,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> Task | None:
        task = await self.task_repository.get_for_update_by_owner(task_id, owner_id)
        if task is None:
            return None

        update_values = {
            field: value
            for field, value in {
                "title": title,
                "description": description,
                "status": status,
            }.items()
            if value is not None
        }

        updated_task = await self.task_repository.update_fields(task, update_values)
        await self.session.commit()
        await self.cache_service.invalidate_owner_tasks(updated_task.owner_id)
        return updated_task
