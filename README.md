# Social Post Scheduler

[![CI](https://github.com/tommyshamamba/ai-social-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/tommyshamamba/ai-social-bot/actions/workflows/ci.yml)

A FastAPI service that drafts short social posts from templates, schedules them, and publishes
due posts through a pluggable publisher interface.

> Portfolio project. The default publisher records posts in memory. No social-network API is
> called, and no audience or engagement figures are claimed.

## What it does

- `POST /drafts` fills a template such as `"Shipping {feature} today"` and enforces the 280-character limit.
- `POST /posts` schedules text for a UTC time. `GET /posts` lists posts in time order, and `DELETE /posts/{id}` cancels one.
- `POST /posts/run-due` publishes every post that is due. A publisher error marks that post `failed`
  with the reason and the rest of the batch continues.
- `GET /stats` counts posts per status. `GET /healthz` is the liveness check.

## Architecture

```
FastAPI ─► Scheduler (thread-safe store, due-post selection, failure isolation)
                 └─► Publisher protocol ─► MemoryPublisher (default) | real API adapter (not included)
```

To connect a real network, implement `publish(text)` and pass it to `Scheduler`. A cron job or
worker can call `run-due` on an interval.

## Run

```sh
pip install -r requirements.txt
uvicorn src.bot:app --reload             # http://localhost:8000/docs
docker build -t post-scheduler . && docker run -p 8000:8000 post-scheduler
```

## Tests

```sh
pip install -r requirements.txt -r requirements-dev.txt
ruff check . && pytest -q
```

The tests cover template rendering, due-time selection, publisher-failure isolation, cancellation
and validation. GitHub Actions runs lint, tests and a Docker build on every push.

## License

MIT
