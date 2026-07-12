from datetime import timedelta, timezone

import pytest

from social_poster.models import Post, PostStatus, utcnow


def make_post(**kw):
    defaults = dict(
        content="hello",
        platforms=["console"],
        scheduled_for=utcnow(),
    )
    defaults.update(kw)
    return Post(**defaults)


def test_empty_content_rejected():
    with pytest.raises(ValueError):
        make_post(content="   ")


def test_no_platform_rejected():
    with pytest.raises(ValueError):
        make_post(platforms=[])


def test_naive_datetime_gets_utc():
    from datetime import datetime

    post = make_post(scheduled_for=datetime(2030, 1, 1, 12, 0, 0))
    assert post.scheduled_for.tzinfo == timezone.utc


def test_is_due():
    past = make_post(scheduled_for=utcnow() - timedelta(minutes=1))
    future = make_post(scheduled_for=utcnow() + timedelta(minutes=1))
    assert past.is_due()
    assert not future.is_due()


def test_published_post_not_due():
    post = make_post(scheduled_for=utcnow() - timedelta(minutes=1))
    post.status = PostStatus.PUBLISHED
    assert not post.is_due()
