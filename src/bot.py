"""Social post scheduler.

A FastAPI service for drafting short social posts from templates, scheduling them, and
publishing due posts through a pluggable publisher. The default publisher only records
posts in memory; no social-network API is called.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

MAX_LEN = 280


class Status(str, Enum):
    scheduled = "scheduled"
    published = "published"
    failed = "failed"


class Post(BaseModel):
    id: str
    text: str
    publish_at: datetime
    status: Status = Status.scheduled
    published_at: datetime | None = None
    error: str | None = None


class SchedulePost(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_LEN)
    publish_at: datetime


class DraftRequest(BaseModel):
    template: str = Field(min_length=1)
    values: dict[str, str] = Field(default_factory=dict)


class Publisher(Protocol):
    def publish(self, text: str) -> None: ...


class MemoryPublisher:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def publish(self, text: str) -> None:
        self.sent.append(text)


def render(template: str, values: dict[str, str]) -> str:
    """Fill {placeholders}; raise ValueError on a missing value or an over-long result."""
    try:
        text = template.format(**values)
    except KeyError as exc:
        raise ValueError(f"missing value for {exc.args[0]}") from exc
    if len(text) > MAX_LEN:
        raise ValueError(f"rendered text is {len(text)} characters; limit is {MAX_LEN}")
    return text


class Scheduler:
    def __init__(self, publisher: Publisher) -> None:
        self.publisher = publisher
        self._posts: dict[str, Post] = {}
        self._lock = threading.Lock()

    def schedule(self, req: SchedulePost) -> Post:
        at = req.publish_at if req.publish_at.tzinfo else req.publish_at.replace(tzinfo=timezone.utc)
        post = Post(id=str(uuid.uuid4()), text=req.text, publish_at=at)
        with self._lock:
            self._posts[post.id] = post
        return post

    def posts(self) -> list[Post]:
        with self._lock:
            return sorted(self._posts.values(), key=lambda p: p.publish_at)

    def cancel(self, post_id: str) -> bool:
        with self._lock:
            post = self._posts.get(post_id)
            if post is None or post.status != Status.scheduled:
                return False
            del self._posts[post_id]
            return True

    def run_due(self, now: datetime | None = None) -> list[Post]:
        """Publish every scheduled post whose time has come. Failures are recorded, not raised."""
        now = now or datetime.now(timezone.utc)
        done: list[Post] = []
        for post in self.posts():
            if post.status != Status.scheduled or post.publish_at > now:
                continue
            try:
                self.publisher.publish(post.text)
                post.status, post.published_at = Status.published, now
            except Exception as exc:  # publisher errors must not stop the batch
                post.status, post.error = Status.failed, str(exc)
            done.append(post)
        return done

    def stats(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Status}
        for post in self.posts():
            counts[post.status.value] += 1
        return counts


scheduler = Scheduler(MemoryPublisher())
app = FastAPI(title="Social post scheduler", version="1.0.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/drafts")
def draft(req: DraftRequest) -> dict[str, str]:
    try:
        return {"text": render(req.template, req.values)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/posts", status_code=201)
def schedule(req: SchedulePost) -> Post:
    return scheduler.schedule(req)


@app.get("/posts")
def list_posts() -> list[Post]:
    return scheduler.posts()


@app.delete("/posts/{post_id}", status_code=204, response_class=Response)
def cancel(post_id: str) -> Response:
    if not scheduler.cancel(post_id):
        raise HTTPException(status_code=404, detail="no scheduled post with that id")
    return Response(status_code=204)


@app.post("/posts/run-due")
def run_due() -> list[Post]:
    return scheduler.run_due()


@app.get("/stats")
def stats() -> dict[str, int]:
    return scheduler.stats()
