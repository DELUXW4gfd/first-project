"""The scheduler ties the queue to the platform adapters.

It finds due posts, publishes each to its target platforms, and records the
result back into the queue. It can run a single pass (:meth:`run_once`) or
loop on an interval (:meth:`run_forever`).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

from .models import Post, PublishResult
from .platforms.base import get_platform
from .queue import PostQueue

logger = logging.getLogger("social_poster.scheduler")


class Scheduler:
    def __init__(
        self,
        queue: PostQueue,
        platform_config: Optional[dict[str, dict]] = None,
        dry_run: bool = False,
    ) -> None:
        """
        :param queue: the post queue to drain.
        :param platform_config: per-platform config, keyed by platform name.
        :param dry_run: if True, route every post through the ``console``
            platform instead of the real targets.
        """
        self.queue = queue
        self.platform_config = platform_config or {}
        self.dry_run = dry_run

    def _publish_post(self, post: Post) -> list[PublishResult]:
        results: list[PublishResult] = []
        targets = ["console"] if self.dry_run else post.platforms
        for name in targets:
            try:
                platform = get_platform(name, self.platform_config.get(name, {}))
                result = platform.publish(post)
            except Exception as exc:  # unknown platform, bad config, etc.
                result = PublishResult(name, success=False, detail=str(exc))
            results.append(result)
            level = logging.INFO if result.success else logging.WARNING
            logger.log(
                level,
                "post %s -> %s: %s (%s)",
                post.id,
                name,
                "ok" if result.success else "FAILED",
                result.detail,
            )
        return results

    def run_once(self, now: Optional[datetime] = None) -> list[tuple[Post, list[PublishResult]]]:
        """Publish every currently-due post. Returns (post, results) pairs.

        A post is marked published only if *all* its targets succeeded;
        otherwise it is marked failed with the collected error details so it
        can be inspected and retried.
        """
        processed: list[tuple[Post, list[PublishResult]]] = []
        for post in self.queue.due(now):
            results = self._publish_post(post)
            if results and all(r.success for r in results):
                self.queue.mark_published(post.id)  # type: ignore[arg-type]
            else:
                errors = "; ".join(
                    f"{r.platform}: {r.detail}" for r in results if not r.success
                )
                self.queue.mark_failed(post.id, errors or "no targets")  # type: ignore[arg-type]
            processed.append((post, results))
        return processed

    def run_forever(self, interval: float = 60.0) -> None:  # pragma: no cover
        """Poll the queue every ``interval`` seconds until interrupted."""
        logger.info("scheduler started (interval=%ss, dry_run=%s)", interval, self.dry_run)
        try:
            while True:
                processed = self.run_once()
                if processed:
                    logger.info("processed %d post(s)", len(processed))
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("scheduler stopped")
