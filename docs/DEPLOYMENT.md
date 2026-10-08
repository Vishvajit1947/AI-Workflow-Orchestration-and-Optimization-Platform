# Deployment Guide

The production stack is three containers on one host, defined in `docker-compose.prod.yml`:

| Service | Image | Exposed |
|---------|-------|---------|
| `frontend` | nginx serving the built React app, reverse-proxying `/api`, `/ws`, `/docs` | port 80 (and 443 if enabled) |
| `backend` | FastAPI on uvicorn, **one worker** | internal only |
| `postgres` | `pgvector/pgvector:pg15` | internal only |

## 1. Server setup

- Linux host with Docker Engine 24+ and the Compose plugin.
- 2 vCPU / 4 GB RAM is enough for the app; add memory if you use local embeddings
  (`EMBEDDING_PROVIDER=local` loads a sentence-transformers model).
- Open ports 80 (and 443 for HTTPS) only.

```bash
git clone <repo-url> ai-orchestrator && cd ai-orchestrator
cp .env.example .env
```

## 2. Configuration

Edit `.env`:

- `POSTGRES_PASSWORD` — required; use a long random value.
- `SECRET_KEY` — replace the default.
- At least one of `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`.
  Routing only selects models whose provider has a key.
- `CORS_ORIGINS` — only needed if the UI is served from a different origin than nginx,
  e.g. `["https://orchestrator.example.com"]`.

`DATABASE_URL` / `DATABASE_URL_SYNC` are set by the compose file to point at the `postgres`
service; values in `.env` are overridden.

See the configuration table in the [README](../README.md#configuration) for all tuning options.

## 3. Launch

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps          # all services healthy
curl http://localhost/health                          # {"status":"ok",...}
```

On start the backend runs `alembic upgrade head`, seeds the model registry and default routing
rules (existing entries are never overwritten), and marks any workflow left running by a previous
process as failed.

## 4. HTTPS

1. Obtain a certificate (e.g. with certbot) and place `fullchain.pem` and `privkey.pem` in `nginx/certs/`.
2. In `nginx/nginx.conf`, uncomment the `listen 443 ssl` server block, set `server_name`, and make the
   port-80 server redirect (`return 301 https://$host$request_uri;`).
3. In `docker-compose.prod.yml`, uncomment the `443` port and the `./nginx/certs` volume.
4. `docker compose -f docker-compose.prod.yml up -d`.

The frontend derives the WebSocket URL from the page, so live status switches to `wss://` automatically.

## 5. Database backups

```bash
# Backup
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U orchestrator -Fc ai_orchestrator > backup-$(date +%F).dump

# Restore (into an empty database)
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U orchestrator -d ai_orchestrator --clean --if-exists < backup-YYYY-MM-DD.dump
```

Schedule the backup with cron and copy dumps off the host.

## 6. Upgrades

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build   # migrations run on backend start
```

Wait for running executions to finish first: executions live in the backend process, and a restart
marks in-flight workflows as failed.

## 7. Monitoring

- `GET /health` — liveness (also used by the container healthcheck).
- `docker compose -f docker-compose.prod.yml logs -f backend` — execution logs include `[EXECUTION]`,
  `[ROUTER]`, `[CACHE HIT]`, `[RETRY]`, `[FALLBACK]` and `[CIRCUIT BREAKER]` lines.
- The **Dashboard** page shows cost, failures, latency percentiles and cache savings; export the data
  as CSV/JSON from there or via `/api/analytics/export`.

## Scaling considerations

- **Run one backend process.** Pause/resume/cancel, live WebSocket status and the circuit breaker are
  held in memory. Several workers or replicas would each see only their own executions, and each would
  mark the others' running workflows as failed on startup. Scaling out requires moving that state to a
  shared store (e.g. Redis pub/sub for status, a queue for executions).
- Within one process, raise `MAX_PARALLEL_STAGES` for wider workflows; the limit is usually provider
  rate limits, not the server.
- Postgres: the `execution_records.created_at` and `execution_id` indexes back the analytics queries;
  for very large histories, archive old execution records.
