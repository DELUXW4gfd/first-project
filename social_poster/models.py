"""Core data models for the posting pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


class PostStatus(str, enum.Enum):
    """Lifecycle state of a queued post."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


def utcnow() -> datetime:
    """Timezone-aware UTC now (used everywhere for consistency)."""
    return datetime.now(timezone.utc)


@dataclass
class Post:
    """A single unit of content targeted at one or more platforms.

    ``scheduled_for`` is stored as a timezone-aware UTC datetime. A post is
    eligible for publishing once ``scheduled_for <= now``.
    """

    content: str
    platforms: list[str]
    scheduled_for: datetime
    id: Optional[int] = None
    status: PostStatus = PostStatus.PENDING
    media_paths: list[str] = field(default_factory=list)
    error: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    published_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("Post content must not be empty")
        if not self.platforms:
            raise ValueError("Post must target at least one platform")
        # Normalise naive datetimes to UTC so comparisons never explode.
        if self.scheduled_for.tzinfo is None:
            self.scheduled_for = self.scheduled_for.replace(tzinfo=timezone.utc)

    def is_due(self, now: Optional[datetime] = None) -> bool:
        now = now or utcnow()
        return self.status == PostStatus.PENDING and self.scheduled_for <= now


@dataclass
class PublishResult:
    """Outcome of publishing a post to a single platform."""

    platform: str
    success: bool
    detail: str = ""
    remote_id: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)
