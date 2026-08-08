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

- **Search**: `GET /api/articles/search?q=...` fetches from GNews, respects limits, and upserts to DB as PENDING.
- **Analyze**: `POST /api/articles/{id}/analyze` publishes job to RabbitMQ.
- **Worker**: Consumes jobs, calls OpenAI, saves structured data and raw JSON to DB.

## Quick Start
```bash
cp .env.example .env
docker compose up -d --build
```
Swagger UI: http://localhost:8000/docs
