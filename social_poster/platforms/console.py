"""A no-network platform that "publishes" by printing.

Perfect for dry runs, local development, and tests. It always succeeds and
records what it would have sent.
"""

from __future__ import annotations

import sys
import uuid

from ..models import Post, PublishResult
from .base import BasePlatform, register


@register("console")
class ConsolePlatform(BasePlatform):
    """Writes the post to stdout instead of a real network."""

    max_length = None

    def publish(self, post: Post) -> PublishResult:
        self.validate(post)
        remote_id = uuid.uuid4().hex[:12]
        stream = self.config.get("stream", sys.stdout)
        print(
            f"[console] ({remote_id}) would post:\n"
            f"  {post.content}",
            file=stream,
        )
        if post.media_paths:
            print(f"  media: {', '.join(post.media_paths)}", file=stream)
        return PublishResult(
            platform=self.name,
            success=True,
            detail="printed to console",
            remote_id=remote_id,
        )
