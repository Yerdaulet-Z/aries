# Aries — News Analyzer

A web app that fetches real-time news articles, uses AI to generate summaries and sentiment analysis, and stores the results in PostgreSQL.

## Architecture

```
┌──────────┐   fetches      ┌──────────────┐
│   API    │───────────────>│  GNews API   │
│ (FastAPI)│   saves        │ (on-demand)  │
└────┬─────┴───────────────>└──────────────┘
     │        (PENDING)      
     │ publishes           
┌────┴───────┐   consumes   ┌──────────────┐
│  RabbitMQ  │─────────────>│    Worker    │
│            │              │  (consumer)  │
└────────────┘              └──────┬───────┘
                                   │ calls
                            ┌──────┴───────┐
                            │    OpenAI    │
                            │  (COMPLETED) │
                            └──────────────┘
```
                                   │ calls
                            ┌──────┴───────┐
                            │    OpenAI    │
                            │  (COMPLETED) │
                            └──────────────┘
```

Aries follows a modular, domain-driven architecture:

1. **FastAPI Web & API (`app/api` & `app/templates`)**: Serves the REST API and the responsive HTMX Web UI. Handles synchronous client requests.
2. **RabbitMQ / Queueing (`app/queue`)**: Handles the asynchronous message passing for the AI analysis pipeline.
3. **Worker (`app/worker`)**: An independent asynchronous process that consumes jobs from RabbitMQ, queries OpenAI, and writes the structured analysis back to PostgreSQL.
4. **PostgreSQL (`app/db`)**: The relational database used to store articles and AI analysis using SQLAlchemy. It features a normalized 1-to-1 relationship between `Article` and `AISummary` tables.
5. **Services (`app/services`)**: Business logic layer separating the external API interactions (GNews, OpenAI) from the routing and database layers.

## Running Locally

1. Create a `.env` file (see `.env.example`).
2. Run `docker compose up -d --build`.
3. The UI will be available at [http://localhost:8000/](http://localhost:8000/).
4. API docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Deployment (Railway)

This repository includes a `railway.json` and a production-ready `Dockerfile`/`docker-compose.yml`.

1. Connect your GitHub repository to Railway.
2. Add a **PostgreSQL** database service in Railway.
3. Add a **RabbitMQ** service in Railway.
4. Set your environment variables (`OPENAI_API_KEY`, `GNEWS_API_KEY`, `DATABASE_URL`, `RABBITMQ_URL`).
5. Deploy! Railway will automatically detect `railway.json` and deploy both the API and Worker alongside the services.

- **Search**: `GET /api/articles/search?q=...` fetches from GNews, respects limits, and upserts to DB as PENDING.
- **Analyze**: `POST /api/articles/{id}/analyze` publishes job to RabbitMQ.
- **Worker**: Consumes jobs, calls OpenAI, saves structured data and raw JSON to DB.

## Quick Start
```bash
cp .env.example .env
docker compose up -d --build
```
Swagger UI: http://localhost:8000/docs
