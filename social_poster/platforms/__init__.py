"""Platform adapters package.

Importing this package registers all built-in platforms so they are
discoverable via :func:`social_poster.platforms.base.get_platform`.
"""

from .base import BasePlatform, available_platforms, get_platform, register

# Import built-in adapters for their registration side effects.
from . import console  # noqa: F401,E402
from . import mastodon  # noqa: F401,E402
from . import twitter  # noqa: F401,E402

__all__ = [
    "BasePlatform",
    "available_platforms",
    "get_platform",
    "register",
]
