"""Command-line interface for the Automated Social Media Posting tool.

Examples
--------
Queue a post for two platforms, five minutes from now::

    python -m social_poster schedule \
        --content "Hello, world!" \
        --platforms twitter,mastodon \
        --in 5m

List everything in the queue::

    python -m social_poster list

Publish all due posts once (dry run prints instead of calling APIs)::

    python -m social_poster run --once --dry-run

Run continuously, checking every 30 seconds::

    python -m social_poster run --interval 30
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime, timedelta, timezone

from .config import Config
from .models import Post, PostStatus, utcnow
from .platforms.base import available_platforms
from .queue import PostQueue
from .scheduler import Scheduler

# Ensure built-in platforms are registered.
from . import platforms  # noqa: F401

_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_when(value: str | None, delay: str | None) -> datetime:
    """Resolve a scheduled time from an ISO timestamp or a relative delay."""
    if delay:
        match = _DURATION_RE.match(delay)
        if not match:
            raise ValueError(f"Invalid --in duration: {delay!r} (try 30s, 5m, 2h, 1d)")
        amount, unit = int(match.group(1)), match.group(2).lower()
        return utcnow() + timedelta(seconds=amount * _UNIT_SECONDS[unit])
    if value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return utcnow()


def _fmt(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ") if dt else "-"


def _open_queue(args: argparse.Namespace) -> PostQueue:
    db = args.database
    if db is None and args.config:
        db = Config.load(args.config).database
    return PostQueue(db or "posts.db")


def _platform_config(args: argparse.Namespace) -> dict[str, dict]:
    return Config.load(args.config).platforms if args.config else {}


def cmd_schedule(args: argparse.Namespace) -> int:
    platforms_list = [p.strip() for p in args.platforms.split(",") if p.strip()]
    if not platforms_list:
        print("error: at least one platform is required", file=sys.stderr)
        return 2
    when = parse_when(args.at, getattr(args, "in"))
    post = Post(
        content=args.content,
        platforms=platforms_list,
        scheduled_for=when,
        media_paths=[m.strip() for m in (args.media or "").split(",") if m.strip()],
    )
    with _open_queue(args) as queue:
        queue.add(post)
    print(f"Scheduled post #{post.id} for {_fmt(post.scheduled_for)} "
          f"-> {', '.join(platforms_list)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    status = PostStatus(args.status) if args.status else None
    with _open_queue(args) as queue:
        posts = queue.list(status)
    if not posts:
        print("(queue is empty)")
        return 0
    print(f"{'ID':>4}  {'STATUS':<10} {'SCHEDULED':<20} {'PLATFORMS':<22} CONTENT")
    for p in posts:
        preview = (p.content[:37] + "...") if len(p.content) > 40 else p.content
        preview = preview.replace("\n", " ")
        print(f"{p.id:>4}  {p.status.value:<10} {_fmt(p.scheduled_for):<20} "
              f"{','.join(p.platforms):<22} {preview}")
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    with _open_queue(args) as queue:
        ok = queue.cancel(args.id)
    if ok:
        print(f"Cancelled post #{args.id}")
        return 0
    print(f"Post #{args.id} not found or not pending", file=sys.stderr)
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    with _open_queue(args) as queue:
        scheduler = Scheduler(
            queue,
            platform_config=_platform_config(args),
            dry_run=args.dry_run,
        )
        if args.once:
            processed = scheduler.run_once()
            ok = sum(1 for _, rs in processed if all(r.success for r in rs))
            print(f"Processed {len(processed)} due post(s); {ok} fully succeeded.")
        else:
            scheduler.run_forever(interval=args.interval)
    return 0


def cmd_platforms(_args: argparse.Namespace) -> int:
    print("Available platforms:")
    for name in available_platforms():
        print(f"  - {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="social_poster",
        description="Automated Social Media Posting — schedule and publish "
        "content across platforms.",
    )
    parser.add_argument("--database", help="path to the SQLite queue (default: posts.db)")
    parser.add_argument("--config", help="path to a JSON/YAML config file")
    parser.add_argument("-v", "--verbose", action="store_true", help="enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sched = sub.add_parser("schedule", help="queue a new post")
    p_sched.add_argument("--content", required=True, help="the post text")
    p_sched.add_argument("--platforms", required=True, help="comma-separated platform names")
    p_sched.add_argument("--at", help="ISO-8601 time to publish (UTC if no tz)")
    p_sched.add_argument("--in", dest="in", help="relative delay, e.g. 30s, 5m, 2h, 1d")
    p_sched.add_argument("--media", help="comma-separated media file paths")
    p_sched.set_defaults(func=cmd_schedule)

    p_list = sub.add_parser("list", help="show queued posts")
    p_list.add_argument("--status", choices=[s.value for s in PostStatus], help="filter by status")
    p_list.set_defaults(func=cmd_list)

    p_cancel = sub.add_parser("cancel", help="cancel a pending post")
    p_cancel.add_argument("id", type=int, help="post id to cancel")
    p_cancel.set_defaults(func=cmd_cancel)

    p_run = sub.add_parser("run", help="publish due posts")
    p_run.add_argument("--once", action="store_true", help="run a single pass and exit")
    p_run.add_argument("--interval", type=float, default=60.0, help="poll interval in seconds")
    p_run.add_argument("--dry-run", action="store_true", help="print instead of calling APIs")
    p_run.set_defaults(func=cmd_run)

    p_plat = sub.add_parser("platforms", help="list available platforms")
    p_plat.set_defaults(func=cmd_platforms)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return args.func(args)
    except (ValueError, KeyError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
