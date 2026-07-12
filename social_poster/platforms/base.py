"""Platform adapter interface and registry.

A *platform* knows how to publish a :class:`Post` to one social network. New
platforms register themselves with :func:`register` and are looked up by name
via :func:`get_platform`, giving the rest of the system a simple plugin model.
"""

from __future__ import annotations

import abc
from typing import Callable, Dict, Type

from ..models import Post, PublishResult

# name -> factory returning a configured BasePlatform instance
_REGISTRY: Dict[str, Callable[[dict], "BasePlatform"]] = {}


class BasePlatform(abc.ABC):
    """Base class every platform adapter must implement."""

    #: Unique short name, e.g. ``"twitter"``. Set by subclasses.
    name: str = ""

    #: Max characters the platform accepts. ``None`` means unlimited.
    max_length: int | None = None

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    def validate(self, post: Post) -> None:
        """Raise ``ValueError`` if the post cannot be published as-is."""
        if self.max_length is not None and len(post.content) > self.max_length:
            raise ValueError(
                f"{self.name}: content is {len(post.content)} chars, "
                f"limit is {self.max_length}"
            )

    @abc.abstractmethod
    def publish(self, post: Post) -> PublishResult:
        """Publish ``post`` and return the outcome. Must not raise for
        expected remote failures — return a failed :class:`PublishResult`
        instead."""
        raise NotImplementedError


def register(name: str) -> Callable[[Type[BasePlatform]], Type[BasePlatform]]:
    """Class decorator that registers a platform under ``name``."""

    def _decorator(cls: Type[BasePlatform]) -> Type[BasePlatform]:
        cls.name = name
        _REGISTRY[name] = cls  # type: ignore[assignment]
        return cls

    return _decorator


def available_platforms() -> list[str]:
    return sorted(_REGISTRY)


def get_platform(name: str, config: dict | None = None) -> BasePlatform:
    """Instantiate a registered platform by name."""
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown platform '{name}'. Available: {', '.join(available_platforms())}"
        ) from None
    return factory(config or {})  # type: ignore[call-arg]
