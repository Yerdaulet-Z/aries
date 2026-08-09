# Aries — Autonomous AI News Analyzer

A modern web application built with Python (FastAPI), HTMX, PostgreSQL, RabbitMQ, and OpenAI. Aries fetches real-time news headlines, orchestrates multi-stage AI summary and sentiment analysis via background queues, and presents an interactive glassmorphic UI.

---

## 🏛️ Project Architecture

```
┌─────────────┐     Search News     ┌──────────────┐
│  HTMX UI    │────────────────────>│  GNews API   │
│ & REST API  │   upserts to DB     │ (on-demand)  │
└──────┬──────┘     (PENDING)       └──────────────┘
       │
       │ Trigger Analysis
       ▼
┌─────────────┐   consumes job    ┌──────────────┐
│  RabbitMQ   │──────────────────>│  AI Worker   │
│  (Queue)    │                   │ (Background) │
└─────────────┘                   └──────┬───────┘
                                         │ Calls
                                  ┌──────┴───────┐
                                  │  OpenAI API  │
                                  │ (gpt-4.1-nano)│
                                  └──────┬───────┘
                                         │ Persists
                                  ┌──────┴───────┐
                                  │  PostgreSQL  │
                                  │  (Database)  │
                                  └──────────────┘
```

Aries is structured cleanly into domain packages:

- **FastAPI Core (`app/api`)**: Serves REST endpoints (`/api/articles`) and HTMX UI views (`/ui/*`).
- **Data Models (`app/db`)**: Clean 1-to-1 normalized relationship between `Article` and `AISummary` models with `ondelete="CASCADE"`.
- **Services (`app/services`)**: Business logic decoupling GNews fetching, OpenAI structured outputs, and PostgreSQL queries.
- **Queue & Worker (`app/core`, `app/worker`)**: Async RabbitMQ publisher and progressive consumer pipeline.
- **Frontend (`app/templates`, `app/static`)**: Glassmorphic single-page application powered by HTMX and Vanilla CSS.

---

## 🌟 Key Features

1. **Discover News Tab**: Search real-time news topics using GNews API. Automatically upserts retrieved articles into PostgreSQL. Already-analyzed articles display their full AI summary and sentiment badge immediately.
2. **Analysis Vault Tab**: Interactive dashboard for all stored articles with full-text GIN search, Enum status filters (Pending, Queued, Extracting, Summarizing, Saving, Completed, Failed), sentiment filters, and custom sorting (Default Analyzed First, Date, Sentiment Score).
3. **Progressive Multi-Stage AI Pipeline**: Visual real-time progress bar tracking the lifecycle of an analysis job:
   - **`QUEUED` (15%)**: Message published to RabbitMQ.
   - **`EXTRACTING_TEXT` (40%)**: Worker extracts & preprocesses content.
   - **`GENERATING_SUMMARY` (75%)**: OpenAI `gpt-4.1-nano` produces structured JSON summary & sentiment score.
   - **`SAVING_RESULTS` (95%)**: Worker persists `AISummary` to PostgreSQL.
   - **`COMPLETED` (100%)**: Final UI render with sentiment pill and summary box.
4. **Cascade Deletion**: Delete any article from the Vault UI or REST API (`DELETE /api/articles/{id}`). Deleting an article automatically cascades and purges its associated `AISummary` record.
5. **High-Frequency 1s Polling**: HTMX polls active cards every 1 second, ensuring smooth, unskipped progress bar animations.

---

## ⚡ REST API Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/articles` | List stored articles (filters: `q`, `status`, `sentiment`, `sort_by`, pagination) |
| `GET` | `/api/articles/{id}` | Get single article by UUID with AI summary |
| `GET` | `/api/articles/search?q=...` | Search GNews API, upsert results to PostgreSQL as PENDING |
| `POST` | `/api/articles/{id}/analyze` | Queue AI analysis job to RabbitMQ (returns `202 Accepted`) |
| `DELETE` | `/api/articles/{id}` | Permanently delete article and cascade delete its `AISummary` |
| `GET` | `/ui/discover` | Render Discover News HTML cards |
| `GET` | `/ui/vault` | Render Analysis Vault HTML cards with filter bar |
| `GET` | `/ui/vault/card/{id}` | Poll single Vault card state for HTMX updates |
| `DELETE` | `/ui/vault/card/{id}` | Delete Vault card and return empty HTML to remove from UI |

---

## 🚀 Running Locally

```bash
# 1. Clone repo & setup environment
cp .env.example .env

# Edit .env with your keys:
# OPENAI_API_KEY=your_openai_api_key_here
# GNEWS_API_KEY=your_gnews_api_key_here

# 2. Start full stack with Docker Compose
docker compose up -d --build
```

- **Web Application UI**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## ☁️ Production Deployment (Railway)

Aries is optimized for single-container Railway deployment with embedded background task handling.

1. Connect your GitHub repository to Railway.
2. Add a **PostgreSQL** database and a **RabbitMQ** service in Railway.
3. Paste the following environment variables in Railway's **Raw Editor**:

```env
OPENAI_API_KEY=your_openai_api_key_here
GNEWS_API_KEY=your_gnews_api_key_here
DATABASE_URL=${{Postgres.DATABASE_URL}}
RABBITMQ_URL=${{RabbitMQ.AMQP_URL}}
GNEWS_RATE_LIMIT=100
WORKER_SLEEP_SECONDS=2
```

4. Click **Generate Domain** under Public Networking to get your public HTTPS URL!
