"""Tests for core engine, events, and config."""

import pytest
from clickml_pro.core.events import EventBus


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event.payload)

        bus.subscribe("test.event", handler)
        bus.publish("test.event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    def test_multiple_subscribers(self):
        bus = EventBus()
        results = []

        bus.subscribe("multi", lambda e: results.append("a"))
        bus.subscribe("multi", lambda e: results.append("b"))
        bus.publish("multi", {})

        assert len(results) == 2
        assert "a" in results
        assert "b" in results

    def test_history(self):
        bus = EventBus()
        bus.publish("h.event", {"x": 1})
        bus.publish("h.event", {"x": 2})

        history = bus.history("h.event")
        assert len(history) == 2

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)

        bus.subscribe("unsub", handler)
        bus.unsubscribe("unsub", handler)
        bus.publish("unsub", {})

        assert len(received) == 0
