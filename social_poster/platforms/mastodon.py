"""Mastodon platform adapter.

Publishes a status via the Mastodon REST API. Credentials are read from the
platform config or the environment:

    MASTODON_API_BASE_URL   e.g. https://mastodon.social
    MASTODON_ACCESS_TOKEN   an application access token

``requests`` is imported lazily so the package works without it installed;
you only need it if you actually publish to Mastodon.
"""

from __future__ import annotations

import os

from ..models import Post, PublishResult
from .base import BasePlatform, register


@register("mastodon")
class MastodonPlatform(BasePlatform):
    # Instances vary, but 500 is the default server limit.
    max_length = 500

    def _credentials(self) -> tuple[str, str]:
        base_url = self.config.get("api_base_url") or os.environ.get(
            "MASTODON_API_BASE_URL", ""
        )
        token = self.config.get("access_token") or os.environ.get(
            "MASTODON_ACCESS_TOKEN", ""
        )
        if not base_url or not token:
            raise ValueError(
                "Mastodon requires api_base_url and access_token "
                "(config or MASTODON_API_BASE_URL / MASTODON_ACCESS_TOKEN)"
            )
        return base_url.rstrip("/"), token

    def publish(self, post: Post) -> PublishResult:
        self.validate(post)
        try:
            base_url, token = self._credentials()
        except ValueError as exc:
            return PublishResult(self.name, success=False, detail=str(exc))

        try:
            import requests  # noqa: PLC0415 (lazy, optional dependency)
        except ImportError:
            return PublishResult(
                self.name,
                success=False,
                detail="the 'requests' package is required to post to Mastodon",
            )

        try:
            resp = requests.post(
                f"{base_url}/api/v1/statuses",
                headers={"Authorization": f"Bearer {token}"},
                data={"status": post.content},
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
        return PublishResult(
            self.name,
            success=True,
            detail="status created",
            remote_id=str(body.get("id", "")),
            raw=body,
        )
