# Docker Setup Guide — NL Database Querying Platform

This walks you from an empty folder to a running dev stack: FastAPI backend (LangGraph/LangChain + Anthropic API), Postgres w/ pgvector, and a Next.js (App Router) + React + Tailwind CSS frontend — all containerized and namespaced by project ID from day one.

---

## 1. Prerequisites

Install:
- **Docker Desktop** (includes Docker Engine + Compose v2) — Mac/Windows. On Linux, install `docker.io` and `docker-compose-plugin` separately.
- Verify:
```bash
docker --version
docker compose version
```
- An **Anthropic API key** (console.anthropic.com)
- Optionally a **LangSmith API key** for observability (smith.langchain.com) — LangSmith itself is a hosted SaaS, so you don't containerize it, just point your app at it via env vars.

---

## 2. Project structure

```
nl-db-platform/
├── docker-compose.yml
├── .env
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   └── app/
│       ├── main.py
│       ├── core/
│       ├── graph/          # LangGraph pipeline (intent → schema link → query gen)
│       ├── db/
│       └── api/
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
```

```bash
mkdir -p nl-db-platform/backend/app/{core,graph,db,api}
mkdir -p nl-db-platform/backend/alembic/versions
mkdir -p nl-db-platform/frontend/src
cd nl-db-platform
```

---

## 3. Environment variables

`.env.example` (commit this; copy to `.env` and fill in secrets, keep `.env` gitignored):

```env
# --- Anthropic ---
ANTHROPIC_API_KEY=sk-ant-xxxx
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_xxxx
LANGCHAIN_PROJECT=nl-db-platform

# --- App DB (metadata: users, projects, connections, chat history) ---
POSTGRES_USER=platform
POSTGRES_PASSWORD=change_me
POSTGRES_DB=platform_db
DATABASE_URL=postgresql+asyncpg://platform:change_me@postgres:5432/platform_db

# --- Vector store (schema embeddings, namespaced per project_id) ---
VECTOR_STORE=pgvector   # or "chroma"


# --- Auth ---
JWT_SECRET_KEY=change_me_too
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# --- Credential encryption for connected end-user databases ---
FERNET_KEY=generate_with_python_cryptography

# --- Frontend ---
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Generate the Fernet key once:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then:
```bash
cp .env.example .env   # fill in real values
```

---

## 4. `docker-compose.yml`

```yaml
services:
  postgres:
    image: ankane/pgvector:latest   # postgres + pgvector extension prebuilt
    container_name: platform_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/db/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10


  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: platform_backend
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: ${DATABASE_URL}
      REDIS_URL: ${REDIS_URL}
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app          # live-reload in dev; remove for prod image
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: platform_frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      - backend
    command: npm run dev

volumes:
  pgdata:
  redisdata:
```

Note: `ankane/pgvector` gives you Postgres with the `pgvector` extension baked in, so you don't need a separate Chroma container unless you decide to switch vector stores later — your architecture already treats that as swappable.

---

## 5. Backend `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg/asyncpg + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/requirements.txt` (starting point — pin versions once you lock them):

```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]
asyncpg
alembic
pydantic-settings
langgraph
langchain
langchain-anthropic
anthropic
pgvector
python-jose[cryptography]
passlib[bcrypt]
cryptography
langsmith
```

---

## 6. Frontend `Dockerfile`

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
```

(This is a dev-mode image with hot reload. For production you'd add a multi-stage Next.js build that runs `npm run build` and serves via `next start` or standalone output.)

If you haven't scaffolded the frontend yet:
```bash
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir
```

---

## 7. First build & run

```bash
docker compose build
docker compose up -d
docker compose ps          # confirm all 4 services are healthy/running
docker compose logs -f backend   # watch startup logs
```

Backend should be reachable at `http://localhost:8000`, frontend at `http://localhost:3000`.

---

## 8. Initialize the database

**Enable pgvector extension** (the base image includes it, but the extension still needs creating per-DB):
```bash
docker compose exec postgres psql -U platform -d platform_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**Set up Alembic** (inside the backend container, so it uses the same env):
```bash
docker compose exec backend alembic init alembic   # skip if already scaffolded
docker compose exec backend alembic revision --autogenerate -m "init schema"
docker compose exec backend alembic upgrade head
```

Your initial migration should include, at minimum:
- `projects` table (this is your namespacing root — every connection, schema-embedding, and chat history row should carry `project_id` as a foreign key from the start)
- `connections` table (encrypted connection strings via `FERNET_KEY`)
- `users` table (OAuth2/JWT)
- a vector table/collection scoped by `project_id` for schema embeddings

---

## 9. Sanity checks

```bash
curl http://localhost:8000/health          # add a simple health route if you don't have one
docker compose exec postgres psql -U platform -d platform_db -c "\dx"   # confirm vector extension listed
docker compose exec redis redis-cli ping   # should return PONG
```

---

## 10. Day-to-day commands

```bash
docker compose up -d              # start everything
docker compose down               # stop (keeps volumes/data)
docker compose down -v            # stop AND wipe volumes (fresh DB)
docker compose logs -f backend    # tail backend logs
docker compose exec backend bash  # shell into backend container
docker compose restart backend    # after dependency changes
```

When you add a Python package: update `requirements.txt`, then `docker compose build backend && docker compose up -d backend`.

---

## 11. Where this leaves you for Phase 1

- All four services run locally with one command.
- `project_id` namespacing is baked into the schema from the first migration, so the later "per-database chatbot" packaging step is deployment/config work, not a rearchitecture.
- LangSmith tracing is wired via env vars so you get pipeline observability (intent node → schema linking → query generation) from day one.

**Next natural step:** scaffold `app/main.py`, the LangGraph pipeline skeleton, and the `projects`/`connections` SQLAlchemy models. Say the word and I'll generate those files directly.
