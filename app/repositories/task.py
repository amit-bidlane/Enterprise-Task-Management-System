from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model=Task)

    async def get_by_owner(self, owner_id: int) -> list[Task]:
        statement = select(Task).where(Task.owner_id == owner_id).order_by(Task.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_for_update(self, task_id: int) -> Task | None:
        statement = select(Task).where(Task.id == task_id).with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_for_update_by_owner(self, task_id: int, owner_id: int) -> Task | None:
        statement = (
            select(Task)
            .where(Task.id == task_id, Task.owner_id == owner_id)
            .with_for_update()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
