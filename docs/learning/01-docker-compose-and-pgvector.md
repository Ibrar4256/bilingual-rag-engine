# 01 — Docker Compose & pgvector

## What it is

**Docker Compose** is a tool that lets you define and run multi-container applications with a single configuration file (`docker-compose.yml`). Instead of manually installing software like PostgreSQL on your machine, you describe what you want in a YAML file and Docker handles the rest — downloading, configuring, starting, and networking everything together.

**pgvector** is an extension for PostgreSQL that adds the ability to store and search **vector embeddings** — lists of numbers that represent the "meaning" of text. Regular PostgreSQL is great at storing rows and columns, but it doesn't know how to answer "find me the 10 most similar items to this one." pgvector adds that capability.

## Real-life analogy

Think of Docker Compose like a **restaurant kitchen setup manual**. Instead of the head chef personally installing every oven, refrigerator, and dishwasher and wiring them together, there's a single instruction sheet that says: "Put oven model X here, fridge model Y there, connect them to power outlet Z." A new chef can walk in, read the sheet, and have an identical kitchen running in minutes.

pgvector is like adding a **"vibe check" filing system** to a traditional library. A normal library (PostgreSQL) organizes books by title, author, and subject — exact categories. pgvector adds a second system where every book also gets a "mood/topic fingerprint" (a vector), and you can ask: "Find me books that *feel like* this one" — even if they don't share the same exact title or author.

## Why we used it here

- **Docker Compose** (satisfies R21): The client requires the ETL pipeline and Search API to be independently Dockerized with a `docker-compose.yml` for local development. By starting with Compose from day one, every developer (or the client) can spin up the exact same environment with `docker compose up`.

- **pgvector** (satisfies R9, R12): The project needs "dual-path indexing" — every category and company record is stored with both a vector embedding (for semantic search: "find companies similar to this description") and BM25 text tokens (for keyword search: "find companies mentioning 'forklift'"). pgvector lets us keep both in one database instead of running a separate vector database like Pinecone or Weaviate.

**File:** `docker-compose.yml`

## Code walkthrough

```yaml
services:
  postgres:
    # This image comes with PostgreSQL 16 AND the pgvector extension pre-installed.
    # Without this specific image, we'd need to install pgvector manually.
    image: pgvector/pgvector:pg16

    # Give the container a predictable name so we can reference it in commands
    # like: docker exec bilingual_postgres psql ...
    container_name: bilingual_postgres

    environment:
      # These env vars tell the Postgres container to automatically create
      # a database called "bilingual_search" with these credentials on first start.
      POSTGRES_USER: bilingual
      POSTGRES_PASSWORD: bilingual
      POSTGRES_DB: bilingual_search

    ports:
      # Map port 5432 inside the container to port 5432 on your machine.
      # This lets Python code running on your machine connect to localhost:5432
      # and reach the Postgres instance inside the container.
      - "5432:5432"

    volumes:
      # Named volume: saves database files to a persistent location on your machine.
      # Without this, stopping the container would DELETE all your data.
      # "pgdata" is just a label — Docker manages the actual folder location.
      - pgdata:/var/lib/postgresql/data

    healthcheck:
      # Docker runs this command every 5 seconds to check if Postgres is ready.
      # Other services can use "depends_on: postgres: condition: service_healthy"
      # to wait until the database is actually accepting connections.
      test: ["CMD-SHELL", "pg_isready -U bilingual -d bilingual_search"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  # Declare the named volume. Docker creates and manages the storage location.
  pgdata:
```

## How to explain this in an interview / to a teammate

"We use Docker Compose to define our local development environment as code — a single `docker-compose.yml` file that anyone can run with `docker compose up` to get an identical setup. Our PostgreSQL database uses the pgvector extension, which adds vector similarity search alongside regular SQL queries. This lets us store both semantic embeddings and keyword-search indexes in one database instead of running a separate vector store. The Compose file also sets up health checks so dependent services know when the database is ready, and uses a named volume so data persists across container restarts."
