"""Automated Social Media Posting.

A lightweight, extensible framework for scheduling and publishing posts to
multiple social media platforms from a single content queue.
"""

from .models import Post, PostStatus, PublishResult
from .queue import PostQueue
from .scheduler import Scheduler

__version__ = "0.1.0"

__all__ = [
    "Post",
    "PostStatus",
    "PublishResult",
    "PostQueue",
    "Scheduler",
    "__version__",
]
