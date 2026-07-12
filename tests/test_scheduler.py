from datetime import timedelta

import pytest

from social_poster.models import Post, PostStatus, PublishResult, utcnow
from social_poster.platforms.base import register, BasePlatform
from social_poster.queue import PostQueue
from social_poster.scheduler import Scheduler


@register("_always_ok")
class AlwaysOk(BasePlatform):
    def publish(self, post):
        return PublishResult(self.name, success=True, detail="ok")


@register("_always_fail")
class AlwaysFail(BasePlatform):
    def publish(self, post):
        return PublishResult(self.name, success=False, detail="nope")


@pytest.fixture
def queue():
    q = PostQueue(":memory:")
    yield q
    q.close()


def make_post(platforms, minutes=-1):
    return Post(
        content="content",
        platforms=list(platforms),
        scheduled_for=utcnow() + timedelta(minutes=minutes),
    )


def test_run_once_publishes_due_post(queue):
    post = queue.add(make_post(["_always_ok"]))
    scheduler = Scheduler(queue)
    processed = scheduler.run_once()
    assert len(processed) == 1
    assert queue.get(post.id).status == PostStatus.PUBLISHED


def test_run_once_skips_future_post(queue):
    post = queue.add(make_post(["_always_ok"], minutes=5))
    scheduler = Scheduler(queue)
    assert scheduler.run_once() == []
    assert queue.get(post.id).status == PostStatus.PENDING


def test_failure_marks_failed(queue):
    post = queue.add(make_post(["_always_fail"]))
    Scheduler(queue).run_once()
    fetched = queue.get(post.id)
    assert fetched.status == PostStatus.FAILED
    assert "nope" in fetched.error


def test_partial_failure_marks_failed(queue):
    post = queue.add(make_post(["_always_ok", "_always_fail"]))
    Scheduler(queue).run_once()
    assert queue.get(post.id).status == PostStatus.FAILED


def test_dry_run_routes_to_console(queue):
    # target a platform that would fail, but dry_run should bypass it
    post = queue.add(make_post(["_always_fail"]))
    scheduler = Scheduler(queue, dry_run=True)
    scheduler.run_once()
    assert queue.get(post.id).status == PostStatus.PUBLISHED


def test_unknown_platform_marks_failed(queue):
    post = queue.add(make_post(["nonexistent_platform"]))
    Scheduler(queue).run_once()
    assert queue.get(post.id).status == PostStatus.FAILED
