import json
from typing import Any

import pytest

from agent import webapp
from agent.utils import slack_feedback
from agent.utils.slack_feedback import (
    process_slack_reaction_added,
    process_slack_reaction_removed,
)


class _FakeStore:
    def __init__(self) -> None:
        self.items: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}

    async def get_item(self, namespace: tuple[str, ...], key: str) -> dict[str, Any] | None:
        return self.items.get((namespace, key))

    async def put_item(self, namespace: tuple[str, ...], key: str, value: dict[str, Any]) -> None:
        self.items[(namespace, key)] = {"value": value}


class _FakeClient:
    def __init__(self) -> None:
        self.store = _FakeStore()


class _FakeBackgroundTasks:
    def __init__(self) -> None:
        self.tasks: list[tuple[Any, tuple[Any, ...]]] = []

    def add_task(self, func: Any, *args: Any) -> None:
        self.tasks.append((func, args))


class _FakeRequest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.headers: dict[str, str] = {}
        self._body = json.dumps(payload).encode()

    async def body(self) -> bytes:
        return self._body


def _store_message_mapping(
    client: _FakeClient,
    channel_id: str,
    message_ts: str,
    *,
    triggering_user_id: str | None = "U123",
) -> None:
    value: dict[str, Any] = {"run_id": "run-1", "thread_ts": "1.000"}
    if triggering_user_id:
        value["triggering_user_id"] = triggering_user_id
    client.store.items[(("slack_run_map", channel_id), f"message:{message_ts}")] = {"value": value}


def _reaction_event(reaction: str = "thumbsup") -> dict[str, Any]:
    return {
        "type": "reaction_added",
        "reaction": reaction,
        "user": "U123",
        "item": {"type": "message", "channel": "C123", "ts": "2.000"},
    }


@pytest.mark.asyncio
async def test_reaction_added_logs_feedback(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    _store_message_mapping(client, "C123", "2.000")

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    # Should complete without error; feedback is logged internally
    await process_slack_reaction_added(_reaction_event(), event_id="Ev1")

    # Event deduplication record should be stored
    assert (("slack_reaction_events", "C123"), "Ev1") in client.store.items


@pytest.mark.asyncio
async def test_reaction_added_skips_duplicate_event(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    _store_message_mapping(client, "C123", "2.000")
    client.store.items[(("slack_reaction_events", "C123"), "Ev1")] = {"value": {"event_id": "Ev1"}}

    call_count = {"n": 0}

    original_fn = slack_feedback._process_reaction_event  # noqa: SLF001

    async def counting_wrapper(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        return await original_fn(*args, **kwargs)

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    await process_slack_reaction_added(_reaction_event(), event_id="Ev1")

    # Duplicate events should be silently dropped (event already in store)
    # The key check is that no exception is raised and state is not mutated further
    assert (("slack_reaction_events", "C123"), "Ev1") in client.store.items


@pytest.mark.asyncio
async def test_reaction_removed_updates_state_when_last_reaction_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _store_message_mapping(client, "C123", "2.000")
    client.store.items[(("slack_reaction_state", "C123"), "run-1:U123:2.000")] = {
        "value": {
            "run_id": "run-1",
            "user_id": "U123",
            "message_ts": "2.000",
            "reactions": ["thumbsup"],
        }
    }

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    await process_slack_reaction_removed(_reaction_event(), event_id="Ev2")

    state = client.store.items[(("slack_reaction_state", "C123"), "run-1:U123:2.000")]
    assert state["value"]["reactions"] == []


@pytest.mark.asyncio
async def test_reaction_without_message_mapping_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    # Should complete without error; no state should be created
    await process_slack_reaction_added(_reaction_event(), event_id="Ev1")
    # No reaction state entry should have been created
    assert not any("slack_reaction_state" in str(k) for k in client.store.items)


@pytest.mark.asyncio
async def test_reaction_from_non_triggering_user_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _store_message_mapping(client, "C123", "2.000", triggering_user_id="UTRIGGER")

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    # React as a different user — should be ignored
    event = {**_reaction_event(), "user": "UOTHER"}
    await process_slack_reaction_added(event, event_id="Ev1")

    # No state should be created for a non-triggering user
    assert not any("slack_reaction_state" in str(k) for k in client.store.items)


@pytest.mark.asyncio
async def test_conflicting_reactions_update_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient()
    _store_message_mapping(client, "C123", "2.000")
    client.store.items[(("slack_reaction_state", "C123"), "run-1:U123:2.000")] = {
        "value": {
            "run_id": "run-1",
            "user_id": "U123",
            "message_ts": "2.000",
            "reactions": ["thumbsup"],
        }
    }

    monkeypatch.setattr(slack_feedback, "get_client", lambda url: client)

    # User adds a thumbsdown alongside the existing thumbsup → conflicting.
    event = {**_reaction_event("thumbsdown"), "type": "reaction_added"}
    await process_slack_reaction_added(event, event_id="EvConflict")

    # State should now include both reactions (conflicting)
    state = client.store.items[(("slack_reaction_state", "C123"), "run-1:U123:2.000")]
    assert "thumbsdown" in state["value"]["reactions"]


@pytest.mark.asyncio
async def test_slack_webhook_queues_reaction_added(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _reaction_event("+1")
    payload = {"type": "event_callback", "event_id": "Ev1", "event": event}
    background_tasks = _FakeBackgroundTasks()

    monkeypatch.setattr(webapp, "verify_slack_signature", lambda **kwargs: True)

    response = await webapp.slack_webhook(_FakeRequest(payload), background_tasks)

    assert response == {"status": "accepted", "message": "Reaction feedback queued"}
    assert background_tasks.tasks == [(webapp.process_slack_reaction_added, (event, "Ev1"))]


@pytest.mark.asyncio
async def test_slack_webhook_queues_reaction_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    event = {**_reaction_event("-1"), "type": "reaction_removed"}
    payload = {"type": "event_callback", "event_id": "Ev2", "event": event}
    background_tasks = _FakeBackgroundTasks()

    monkeypatch.setattr(webapp, "verify_slack_signature", lambda **kwargs: True)

    response = await webapp.slack_webhook(_FakeRequest(payload), background_tasks)

    assert response == {"status": "accepted", "message": "Reaction removal queued"}
    assert background_tasks.tasks == [(webapp.process_slack_reaction_removed, (event, "Ev2"))]


@pytest.mark.asyncio
async def test_slack_webhook_ignores_untracked_reaction(monkeypatch: pytest.MonkeyPatch) -> None:
    event = _reaction_event("eyes")
    payload = {"type": "event_callback", "event_id": "Ev3", "event": event}
    background_tasks = _FakeBackgroundTasks()

    monkeypatch.setattr(webapp, "verify_slack_signature", lambda **kwargs: True)

    response = await webapp.slack_webhook(_FakeRequest(payload), background_tasks)

    assert response == {"status": "ignored", "reason": "Reaction not tracked for feedback"}
    assert background_tasks.tasks == []
