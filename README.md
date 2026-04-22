# Enterprise Task Management System

A full-stack task management platform built with FastAPI, PostgreSQL, Redis, Celery, and React. The project is structured to reflect production-oriented backend engineering patterns such as the service-repository pattern, async SQLAlchemy, JWT auth with refresh-token rotation, Redis-backed revocation and caching, background workers, and CI-driven testing.

## Tech Stack

### Backend
- FastAPI
- SQLAlchemy 2.0 with async sessions
- Alembic
- PostgreSQL 15
- Redis
- Celery
- Passlib + bcrypt
- PyJWT

### Frontend
- React
- Vite
- TanStack Query
- React Router

### Quality
- Pytest
- HTTPX
- Ruff
- GitHub Actions

## Features

- JWT authentication with access and refresh tokens
- Refresh-token rotation and Redis-backed token blacklisting
- Service-repository architecture for clean separation of concerns
- Async PostgreSQL access with SQLAlchemy 2.0
- Task update locking with `SELECT ... FOR UPDATE`
- Redis caching for `GET /tasks` with cache invalidation on writes
- Celery background task for simulated assignment email notifications
- React dashboard with optimistic task completion updates
- Automatic frontend token refresh when access tokens expire
- CI pipeline for linting, migrations, and test execution

## Project Structure

```text
.
|-- alembic/
|-- app/
|   |-- api/
|   |-- core/
|   |-- db/
|   |-- models/
|   |-- repositories/
|   |-- schemas/
|   |-- services/
|   |-- tasks/
|   `-- worker.py
|-- frontend/
|-- tests/
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
`-- pyproject.toml
```

## Architecture Overview

### Backend Flow

1. FastAPI routes receive requests.
2. Dependencies resolve the DB session, Redis client, and authenticated user.
3. Services contain business logic.
4. Repositories encapsulate direct database access.
5. Redis is used for both token revocation and task-list caching.
6. Celery handles asynchronous email notification jobs.

### Auth Flow

- `POST /auth/login` issues:
  - access token: 15 minutes
  - refresh token: 7 days
- `POST /auth/refresh` rotates tokens and blacklists the old refresh token
- `POST /auth/logout` blacklists the current access token
- `GET /auth/me` validates JWT, checks Redis revocation, and confirms the user exists in PostgreSQL

### Task Flow

- `GET /tasks` reads from Redis cache first, then falls back to PostgreSQL
- `POST /tasks` creates a task, invalidates cache, and dispatches a Celery notification job
- `PATCH /tasks/{task_id}` updates with row-level locking and invalidates cache

## Environment Variables

Create a `.env` file in the project root. A sample is already included in `.env.example`.

### Backend

```env
APP_NAME=Enterprise Task Management System
APP_ENV=development
APP_PORT=8000

POSTGRES_DB=enterprise_task_management
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

TASK_CACHE_TTL_SECONDS=300
CELERY_BROKER_URL=redis://redis:6379/0
FRONTEND_ORIGIN=http://localhost:5173
```

### Frontend

Create `frontend/.env` from `frontend/.env.example`.

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Running with Docker

### 1. Start the backend stack

```bash
docker-compose up --build
```

This starts:

- `db` on PostgreSQL 15
- `redis` for caching, token revocation, and Celery broker/backend
- `app` for FastAPI
- `worker` for Celery background jobs

### 2. Run migrations

If the app container is already up:

```bash
docker-compose exec app alembic upgrade head
```

### 3. Open the services

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Frontend dev server: `http://localhost:5173`

## Running the Frontend Locally

From the `frontend/` folder:

```bash
npm install
npm run dev
```

The frontend talks to the FastAPI app using `VITE_API_BASE_URL`.

## Running the Backend Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
alembic upgrade head
```

Run the app:

```bash
uvicorn app.main:app --reload
```

Run the worker:

```bash
celery -A app.worker.celery_app worker --loglevel=info
```

## API Endpoints

### Health

- `GET /health`

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

### Tasks

- `GET /tasks`
- `POST /tasks`
- `PATCH /tasks/{task_id}`

## Testing

Run the test suite:

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=100
```

Run linting:

```bash
ruff check .
```

## CI/CD

GitHub Actions workflow:

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

The pipeline:

1. Starts PostgreSQL and Redis services
2. Installs dependencies
3. Runs `ruff`
4. Applies Alembic migrations
5. Runs pytest with a `100%` coverage gate

## Notes

- The current email notification flow is simulated through a Celery task.
- Redis is used in two roles: auth-session revocation and task caching.
- The frontend uses optimistic UI for task completion updates via TanStack Query.
- Automatic JWT refresh is handled client-side in the shared API client.

## Future Enhancements

- Role-based access control
- Team and project workspaces
- Task assignment to other users from the dashboard
- Observability with structured logging and metrics
- Containerized frontend deployment
