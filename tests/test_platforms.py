import io

import pytest

from social_poster.models import Post, PublishResult, utcnow
from social_poster.platforms.base import (
    available_platforms,
    get_platform,
    register,
    BasePlatform,
)


def make_post(content="hi", platforms=("console",)):
    return Post(content=content, platforms=list(platforms), scheduled_for=utcnow())


def test_builtin_platforms_registered():
    names = available_platforms()
    assert {"console", "mastodon", "twitter"} <= set(names)


def test_console_publishes_to_stream():
    stream = io.StringIO()
    platform = get_platform("console", {"stream": stream})
    result = platform.publish(make_post(content="hello there"))
    assert result.success
    assert "hello there" in stream.getvalue()
    assert result.remote_id


def test_unknown_platform_raises():
    with pytest.raises(KeyError):
        get_platform("myspace")


def test_max_length_validation():
    platform = get_platform("twitter")
    long_post = make_post(content="x" * 281, platforms=["twitter"])
    with pytest.raises(ValueError):
        platform.validate(long_post)


def test_missing_credentials_returns_failed_result(monkeypatch):
    monkeypatch.delenv("TWITTER_BEARER_TOKEN", raising=False)
    platform = get_platform("twitter")
    result = platform.publish(make_post(content="short", platforms=["twitter"]))
    assert not result.success
    assert "bearer_token" in result.detail.lower() or "token" in result.detail.lower()


def test_mastodon_missing_credentials(monkeypatch):
    monkeypatch.delenv("MASTODON_API_BASE_URL", raising=False)
    monkeypatch.delenv("MASTODON_ACCESS_TOKEN", raising=False)
    platform = get_platform("mastodon")
    result = platform.publish(make_post(content="hi", platforms=["mastodon"]))
    assert not result.success


def test_custom_platform_registration():
    @register("_test_dummy")
    class Dummy(BasePlatform):
        def publish(self, post):
            return PublishResult(self.name, success=True, detail="ok")

    platform = get_platform("_test_dummy")
    assert platform.publish(make_post()).success
    assert platform.name == "_test_dummy"
