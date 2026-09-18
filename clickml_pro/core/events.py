"""
Simple in-process event bus for decoupled communication between subsystems.

Subsystems publish events (e.g. ``training.started``, ``schema.changed``)
and other subsystems subscribe to react without tight coupling.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field


class Event(BaseModel):
    """An immutable event record."""

    topic: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""


# Type alias for handlers
EventHandler = Callable[[Event], Any]


class EventBus:
    """Publish / subscribe event bus — supports sync and async handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._history: list[Event] = []

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers[topic].append(handler)

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        self._handlers[topic] = [h for h in self._handlers[topic] if h is not handler]

    def publish(self, topic: str, payload: dict[str, Any] | None = None, source: str = "") -> Event:
        event = Event(topic=topic, payload=payload or {}, source=source)
        self._history.append(event)

        for handler in self._handlers.get(topic, []):
            result = handler(event)
            # If the handler is async, schedule it
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    asyncio.run(result)

        # Also fire wildcard handlers
        for handler in self._handlers.get("*", []):
            handler(event)

        return event

    def history(self, topic: str | None = None, limit: int = 100) -> list[Event]:
        events = self._history if topic is None else [e for e in self._history if e.topic == topic]
        return events[-limit:]

    def clear(self) -> None:
        self._handlers.clear()
        self._history.clear()


# Global singleton
_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
