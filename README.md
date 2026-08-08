# Aries — News Analyzer

A web app that fetches real-time news articles, uses AI to generate summaries and sentiment analysis, and stores the results in PostgreSQL.

## Architecture

```
┌──────────┐     saves      ┌────────────┐
│  Poller  │───────────────>│ PostgreSQL │
│ (daemon) │  (PENDING)     │   (DB)     │
└──────────┘                └─────┬──────┘
       polls GNews                │
                                  │ reads
┌──────────┐   publishes    ┌─────┴──────┐
│   API    │──────────────>│  RabbitMQ  │
│ (FastAPI)│  (analyze)     └─────┬──────┘
└──────────┘                      │ consumes
                            ┌─────┴──────┐
                            │   Worker   │───> OpenAI
                            │ (consumer) │───> PostgreSQL (COMPLETED)
                            └────────────┘
```

| Container  | Role                                      | Port  |
|------------|-------------------------------------------|-------|
| `db`       | PostgreSQL 17                             | 5432  |
| `rabbitmq` | Message broker + management UI            | 5672 / 15672 |
| `api`      | FastAPI REST server                       | 8000  |
| `poller`   | Background GNews fetcher (saves to DB)    | —     |
| `worker`   | AI analysis consumer (OpenAI → DB)        | —     |

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — add your API keys:
#   OPENAI_API_KEY=sk-...
#   GNEWS_API_KEY=...
#   GNEWS_RATE_LIMIT=2          # start small
#   WORKER_SLEEP_SECONDS=2      # throttle AI calls
```

### 2. Start the entire stack

```bash
docker compose up -d --build
```

All 5 containers start automatically. Swagger UI: http://localhost:8000/docs

### 3. Verify it works

```bash
# Check poller logs (should show articles being saved)
docker compose logs poller

# List fetched articles
curl http://localhost:8000/api/articles

# Trigger AI analysis on article #1
curl -X POST http://localhost:8000/api/articles/1/analyze

# Check worker logs (should show OpenAI call)
docker compose logs worker

# View the analyzed article
curl http://localhost:8000/api/articles/1
```

## API Endpoints

| Method | Path                          | Description                              |
|--------|-------------------------------|------------------------------------------|
| `GET`  | `/api/articles`               | List articles (filters: q, status, dates)|
| `GET`  | `/api/articles/{id}`          | Get single article with analysis         |
| `POST` | `/api/articles/{id}/analyze`  | Trigger AI analysis (returns 202)        |

### Query Parameters (GET /api/articles)

| Param        | Type     | Description                                |
|--------------|----------|--------------------------------------------|
| `q`          | string   | Full-text search (uses GIN index)          |
| `status`     | enum     | PENDING / QUEUED / PROCESSING / COMPLETED / FAILED |
| `start_date` | datetime | Filter: published_at >= value              |
| `end_date`   | datetime | Filter: published_at <= value              |
| `limit`      | int      | Page size (default: 20, max: 100)          |
| `offset`     | int      | Pagination offset                          |

## Configuration

| Variable              | Default | Description                                |
|-----------------------|---------|--------------------------------------------|
| `GNEWS_RATE_LIMIT`    | 100     | Max articles to fetch per day              |
| `WORKER_SLEEP_SECONDS`| 2       | Seconds to wait between AI analysis jobs   |
| `OPENAI_API_KEY`      | —       | Your OpenAI API key                        |
| `GNEWS_API_KEY`       | —       | Your GNews API key                         |

The poller reads `GNEWS_RATE_LIMIT` dynamically from the mounted `.env` file.
You can change it while the containers are running — no restart needed.

## Database

Tables and indexes are created automatically on startup.

- **GIN full-text index** on title + description
- **B-tree indexes** on `published_at` (desc) and `analysis_status`
- **`updated_at` trigger** managed by PostgreSQL (not ORM)
- **Unique constraint** on `url` for deduplication

## Tech Stack

- **API**: FastAPI (async Python)
- **Database**: PostgreSQL 17 (async via asyncpg + SQLAlchemy 2.0)
- **Queue**: RabbitMQ 4 (via aio-pika)
- **AI**: OpenAI gpt-4.1-nano (structured JSON output)
- **News**: GNews API
