"""SQLite-backed durable queue for scheduled posts.

The queue is intentionally dependency-free (stdlib ``sqlite3``) so it runs
anywhere Python does. All timestamps are stored as ISO-8601 UTC strings.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .models import Post, PostStatus, utcnow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content       TEXT    NOT NULL,
    platforms     TEXT    NOT NULL,
    media_paths   TEXT    NOT NULL DEFAULT '[]',
    scheduled_for TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'pending',
    error         TEXT,
    created_at    TEXT    NOT NULL,
    published_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_due ON posts (status, scheduled_for);
"""


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class PostQueue:
    """A durable, ordered queue of posts backed by SQLite.

    Use as a context manager or call :meth:`close` when done. Pass
    ``":memory:"`` as the path for an ephemeral in-memory queue (handy in
    tests).
    """

    def __init__(self, path: str | Path = "posts.db") -> None:
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> "PostQueue":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._conn.close()

    # -- row mapping -------------------------------------------------------
    @staticmethod
    def _row_to_post(row: sqlite3.Row) -> Post:
        post = Post(
            content=row["content"],
            platforms=json.loads(row["platforms"]),
            scheduled_for=_from_iso(row["scheduled_for"]),  # type: ignore[arg-type]
            media_paths=json.loads(row["media_paths"]),
        )
        post.id = row["id"]
        post.status = PostStatus(row["status"])
        post.error = row["error"]
        post.created_at = _from_iso(row["created_at"])  # type: ignore[assignment]
        post.published_at = _from_iso(row["published_at"])
        return post

    # -- writes ------------------------------------------------------------
    def add(self, post: Post) -> Post:
        """Insert a post and return it with its assigned ``id``."""
        cur = self._conn.execute(
            """
            INSERT INTO posts
                (content, platforms, media_paths, scheduled_for,
                 status, error, created_at, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                post.content,
                json.dumps(post.platforms),
                json.dumps(post.media_paths),
                _to_iso(post.scheduled_for),
                post.status.value,
                post.error,
                _to_iso(post.created_at),
                _to_iso(post.published_at),
            ),
        )
        self._conn.commit()
        post.id = cur.lastrowid
        return post

    def mark_published(self, post_id: int) -> None:
        self._conn.execute(
            "UPDATE posts SET status = ?, published_at = ?, error = NULL WHERE id = ?",
            (PostStatus.PUBLISHED.value, _to_iso(utcnow()), post_id),
        )
        self._conn.commit()

    def mark_failed(self, post_id: int, error: str) -> None:
        self._conn.execute(
            "UPDATE posts SET status = ?, error = ? WHERE id = ?",
            (PostStatus.FAILED.value, error, post_id),
        )
        self._conn.commit()

    def cancel(self, post_id: int) -> bool:
        """Cancel a pending post. Returns True if a post was cancelled."""
        cur = self._conn.execute(
            "UPDATE posts SET status = ? WHERE id = ? AND status = ?",
            (PostStatus.CANCELLED.value, post_id, PostStatus.PENDING.value),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # -- reads -------------------------------------------------------------
    def get(self, post_id: int) -> Optional[Post]:
        row = self._conn.execute(
            "SELECT * FROM posts WHERE id = ?", (post_id,)
        ).fetchone()
        return self._row_to_post(row) if row else None

    def due(self, now: Optional[datetime] = None) -> Iterator[Post]:
        """Yield pending posts whose scheduled time has arrived, oldest first."""
        now = now or utcnow()
        rows = self._conn.execute(
            """
            SELECT * FROM posts
            WHERE status = ? AND scheduled_for <= ?
            ORDER BY scheduled_for ASC, id ASC
            """,
            (PostStatus.PENDING.value, _to_iso(now)),
        ).fetchall()
        for row in rows:
            yield self._row_to_post(row)

    def list(self, status: Optional[PostStatus] = None) -> list[Post]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM posts ORDER BY scheduled_for ASC, id ASC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE status = ? ORDER BY scheduled_for ASC, id ASC",
                (status.value,),
            ).fetchall()
        return [self._row_to_post(r) for r in rows]
