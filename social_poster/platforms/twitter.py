"""Twitter / X platform adapter.

Publishes a tweet via the X API v2 ``POST /2/tweets`` endpoint using an OAuth2
bearer token. Credentials come from config or the environment:

    TWITTER_BEARER_TOKEN    an OAuth2 user-context bearer token

Note: the v2 create-tweet endpoint requires a *user-context* token (OAuth2
Authorization Code with PKCE or OAuth1.0a). A plain app-only bearer token can
read but not post; this adapter surfaces the API's error in that case.

``requests`` is imported lazily so the package works without it installed.
"""

from __future__ import annotations

import os

from ..models import Post, PublishResult
from .base import BasePlatform, register


@register("twitter")
class TwitterPlatform(BasePlatform):
    max_length = 280

    def _token(self) -> str:
        token = self.config.get("bearer_token") or os.environ.get(
            "TWITTER_BEARER_TOKEN", ""
        )
        if not token:
            raise ValueError(
                "Twitter requires a bearer_token "
                "(config or TWITTER_BEARER_TOKEN)"
            )
        return token

    def publish(self, post: Post) -> PublishResult:
        self.validate(post)
        try:
            token = self._token()
        except ValueError as exc:
            return PublishResult(self.name, success=False, detail=str(exc))

        try:
            import requests  # noqa: PLC0415 (lazy, optional dependency)
        except ImportError:
            return PublishResult(
                self.name,
                success=False,
                detail="the 'requests' package is required to post to Twitter",
            )

        try:
            resp = requests.post(
                "https://api.twitter.com/2/tweets",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"text": post.content},
                timeout=self.config.get("timeout", 30),
            )
        except Exception as exc:  # network / connection errors
            return PublishResult(self.name, success=False, detail=str(exc))

        if resp.status_code >= 400:
            return PublishResult(
                self.name,
                success=False,
                detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        body = resp.json()
        data = body.get("data", {})
        return PublishResult(
            self.name,
            success=True,
            detail="tweet created",
            remote_id=str(data.get("id", "")),
            raw=body,
        )
