from app.models.task import Task
from app.models.user import User
from app.repositories.base import BaseRepository
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository


async def create_user(session, email: str = "repo@example.com") -> User:
    user = User(
        email=email,
        full_name="Repo User",
        password_hash="hashed-password",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_task(session, owner_id: int, title: str = "Repository task") -> Task:
    task = Task(
        title=title,
        description="Repository flow",
        status="pending",
        owner_id=owner_id,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def test_base_repository_crud_methods(db_session) -> None:
    repository = BaseRepository(db_session, User)
    user = User(
        email="base@example.com",
        full_name="Base User",
        password_hash="hashed-password",
    )

    created = await repository.add(user)
    await db_session.commit()

    fetched = await repository.get_by_id(created.id)
    listed = await repository.list_all()
    updated = await repository.update_fields(created, {"full_name": "Updated User"})

    assert fetched is not None
    assert len(listed) == 1
    assert updated.full_name == "Updated User"

    await repository.delete(updated)
    await db_session.commit()
    assert await repository.get_by_id(created.id) is None


async def test_user_repository_getters_and_creator(db_session) -> None:
    repository = UserRepository(db_session)

    created = await repository.create_user(
        email="userrepo@example.com",
        full_name="User Repo",
        password_hash="hashed-password",
    )
    await db_session.commit()

    by_id = await repository.get_by_id(created.id)
    by_email = await repository.get_by_email("userrepo@example.com")

    assert by_id is not None
    assert by_email is not None
    assert by_email.email == "userrepo@example.com"


async def test_task_repository_queries_and_locking(db_session) -> None:
    user = await create_user(db_session, email="taskrepo@example.com")
    task = await create_task(db_session, owner_id=user.id)
    repository = TaskRepository(db_session)

    owner_tasks = await repository.get_by_owner(user.id)
    locked_task = await repository.get_for_update(task.id)
    locked_owned_task = await repository.get_for_update_by_owner(task.id, user.id)
    missing_owned_task = await repository.get_for_update_by_owner(task.id, user.id + 99)

    assert len(owner_tasks) == 1
    assert owner_tasks[0].id == task.id
    assert locked_task is not None
    assert locked_owned_task is not None
    assert missing_owned_task is None
