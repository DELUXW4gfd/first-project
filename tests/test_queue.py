from datetime import timedelta

import pytest

from social_poster.models import Post, PostStatus, utcnow
from social_poster.queue import PostQueue


@pytest.fixture
def queue():
    q = PostQueue(":memory:")
    yield q
    q.close()


def make_post(minutes=0, **kw):
    defaults = dict(
        content="hello world",
        platforms=["console"],
        scheduled_for=utcnow() + timedelta(minutes=minutes),
    )
    defaults.update(kw)
    return Post(**defaults)


def test_add_assigns_id_and_roundtrips(queue):
    post = queue.add(make_post())
    assert post.id is not None
    fetched = queue.get(post.id)
    assert fetched.content == "hello world"
    assert fetched.platforms == ["console"]
    assert fetched.status == PostStatus.PENDING


def test_due_returns_only_past_pending(queue):
    past = queue.add(make_post(minutes=-5))
    queue.add(make_post(minutes=5))  # future
    due = list(queue.due())
    assert [p.id for p in due] == [past.id]


def test_due_ordered_oldest_first(queue):
    a = queue.add(make_post(minutes=-1))
    b = queue.add(make_post(minutes=-10))
    due = list(queue.due())
    assert [p.id for p in due] == [b.id, a.id]


def test_mark_published(queue):
    post = queue.add(make_post(minutes=-1))
    queue.mark_published(post.id)
    fetched = queue.get(post.id)
    assert fetched.status == PostStatus.PUBLISHED
    assert fetched.published_at is not None
    assert list(queue.due()) == []


def test_mark_failed_records_error(queue):
    post = queue.add(make_post(minutes=-1))
    queue.mark_failed(post.id, "boom")
    fetched = queue.get(post.id)
    assert fetched.status == PostStatus.FAILED
    assert fetched.error == "boom"


def test_cancel_pending(queue):
    post = queue.add(make_post(minutes=5))
    assert queue.cancel(post.id) is True
    assert queue.get(post.id).status == PostStatus.CANCELLED
    # cancelling again is a no-op
    assert queue.cancel(post.id) is False


def test_list_filter_by_status(queue):
    p1 = queue.add(make_post(minutes=-1))
    queue.add(make_post(minutes=5))
    queue.mark_published(p1.id)
    published = queue.list(PostStatus.PUBLISHED)
    assert [p.id for p in published] == [p1.id]
    assert len(queue.list()) == 2


def test_persists_to_disk(tmp_path):
    db = tmp_path / "posts.db"
    with PostQueue(db) as q:
        pid = q.add(make_post()).id
    with PostQueue(db) as q:
        assert q.get(pid) is not None
