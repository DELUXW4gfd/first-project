# Automated Social Media Posting

A lightweight, extensible framework for **scheduling** and **publishing** posts
across multiple social media platforms from a single content queue.

Queue up content once, target several networks, and let the scheduler publish
each post when its time arrives. The core runs on the Python **standard library
alone** — no dependencies required until you actually publish to a live network.

## Features

- 🗓️ **Durable scheduling** — posts live in a SQLite queue and survive restarts.
- 🔌 **Pluggable platforms** — ship with Twitter/X, Mastodon, and a console
  (dry-run) adapter; add your own with a single decorator.
- 🎯 **Multi-target posts** — one post can fan out to many platforms at once.
- 🧪 **Dry-run mode** — preview exactly what would be sent without calling any API.
- ✅ **Per-platform validation** — character limits are enforced before sending.
- 🔐 **Secrets stay out of code** — credentials come from environment variables.
- 🖥️ **Simple CLI** — `schedule`, `list`, `cancel`, `run`, `platforms`.

## Installation

```bash
git clone https://github.com/deluxw4gfd/first-project.git
cd first-project

# Core only (stdlib) — enough for dry runs and the full test suite:
pip install -e .

# To publish to live networks and/or use YAML config:
pip install -e ".[http,yaml]"
```

Requires Python 3.9+.

## Quick start

Everything works out of the box in dry-run / console mode:

```bash
# See which platforms are available
python -m social_poster platforms

# Queue a post for 5 minutes from now, targeting the console adapter
python -m social_poster schedule \
    --content "Hello, world! 👋" \
    --platforms console \
    --in 5m

# Inspect the queue
python -m social_poster list

# Publish everything that's due, right now, as a dry run
python -m social_poster run --once --dry-run
```

## Usage

### Schedule a post

```bash
python -m social_poster schedule \
    --content "New blog post is live!" \
    --platforms twitter,mastodon \
    --in 2h                       # or: --at 2026-07-12T18:30:00
```

`--in` accepts relative durations: `30s`, `5m`, `2h`, `1d`. `--at` accepts an
ISO-8601 timestamp (assumed UTC if no timezone is given). Omit both to publish
on the next run. Attach media with `--media path/one.png,path/two.jpg`.

### List and cancel

```bash
python -m social_poster list                 # everything
python -m social_poster list --status pending
python -m social_poster cancel 3             # cancel post #3
```

### Run the scheduler

```bash
# One pass, then exit (ideal for cron / GitHub Actions)
python -m social_poster run --once

# Long-running worker, checking every 30 seconds
python -m social_poster run --interval 30

# Preview without hitting any network
python -m social_poster run --once --dry-run
```

A post is marked **published** only if *every* target succeeds; otherwise it is
marked **failed** with the collected error detail so you can inspect and retry.

## Configuration

Non-secret settings live in a JSON or YAML file (see `config.example.json`):

```json
{
  "database": "posts.db",
  "platforms": {
    "mastodon": { "api_base_url": "https://mastodon.social" },
    "twitter":  {}
  }
}
```

Pass it with `--config config.json`. **Credentials are never stored in config** —
adapters read them from the environment (see `.env.example`):

| Platform | Environment variables |
|----------|-----------------------|
| Mastodon | `MASTODON_API_BASE_URL`, `MASTODON_ACCESS_TOKEN` |
| Twitter/X | `TWITTER_BEARER_TOKEN` (user-context OAuth2 token) |

> **Note on Twitter/X:** the v2 "create tweet" endpoint needs a *user-context*
> token (OAuth2 Authorization-Code-with-PKCE or OAuth1.0a). A plain app-only
> bearer token can read but not post.

## Adding a new platform

Adapters are plugins. Subclass `BasePlatform`, register a name, implement
`publish`, and it's instantly available to the CLI and scheduler:

```python
from social_poster.models import Post, PublishResult
from social_poster.platforms.base import BasePlatform, register


@register("bluesky")
class BlueskyPlatform(BasePlatform):
    max_length = 300

    def publish(self, post: Post) -> PublishResult:
        self.validate(post)          # enforces max_length
        # ... call the network's API ...
        return PublishResult("bluesky", success=True, remote_id="abc123")
```

Import your module before use (or add it to
`social_poster/platforms/__init__.py`) so its `@register` runs.

## Architecture

```
CLI  ─┐
      ├─►  Scheduler  ──►  PostQueue (SQLite)
Cron ─┘        │
               └──►  Platform adapters  ──►  Twitter · Mastodon · Console · …
```

- **`models.py`** — `Post`, `PostStatus`, `PublishResult` data types.
- **`queue.py`** — durable SQLite-backed `PostQueue`.
- **`platforms/`** — adapter base class, registry, and built-in adapters.
- **`scheduler.py`** — drains due posts and records results.
- **`cli.py`** — the `social_poster` command-line interface.

## Running the tests

```bash
pip install pytest
pytest
```

The test suite runs entirely offline — no network access or credentials needed.

## License

MIT — see [LICENSE](LICENSE).
