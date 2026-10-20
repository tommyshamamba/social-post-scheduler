from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.bot import MemoryPublisher, Scheduler, SchedulePost, app, render

client = TestClient(app)
NOW = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)


def test_render_fills_placeholders():
    assert render("Hello {name}", {"name": "team"}) == "Hello team"


def test_render_rejects_missing_and_long():
    with pytest.raises(ValueError):
        render("Hi {who}", {})
    with pytest.raises(ValueError):
        render("{x}", {"x": "a" * 281})


def test_run_due_publishes_only_due_posts():
    pub = MemoryPublisher()
    s = Scheduler(pub)
    s.schedule(SchedulePost(text="due", publish_at=NOW - timedelta(minutes=1)))
    s.schedule(SchedulePost(text="later", publish_at=NOW + timedelta(hours=1)))
    done = s.run_due(NOW)
    assert [p.text for p in done] == ["due"]
    assert pub.sent == ["due"]
    assert s.stats() == {"scheduled": 1, "published": 1, "failed": 0}


def test_publisher_failure_is_recorded():
    class Broken:
        def publish(self, text):
            raise RuntimeError("rate limited")

    s = Scheduler(Broken())
    s.schedule(SchedulePost(text="x", publish_at=NOW))
    [post] = s.run_due(NOW)
    assert post.status == "failed" and post.error == "rate limited"


def test_api_schedule_list_cancel():
    body = {"text": "hello", "publish_at": "2030-01-01T00:00:00Z"}
    post = client.post("/posts", json=body).json()
    assert any(p["id"] == post["id"] for p in client.get("/posts").json())
    assert client.delete(f"/posts/{post['id']}").status_code == 204
    assert client.delete(f"/posts/{post['id']}").status_code == 404


def test_api_validation():
    assert client.post("/posts", json={"text": "", "publish_at": "2030-01-01T00:00:00Z"}).status_code == 422
    assert client.post("/drafts", json={"template": "{a}"}).status_code == 422
