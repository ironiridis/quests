"""NPC notification event helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import EVENT_NPC_NOTIFICATION
from .models import Quest


def async_fire_task_state_event(
    hass: HomeAssistant,
    quest: Quest,
    *,
    event_type: str,
    actor_user_id: str | None = None,
    actor_name: str | None = None,
    target_user_ids: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Fire per-user NPC notification events for a task state transition."""
    if quest.disabled and event_type != "disabled":
        return

    payload = {
        "realm_id": quest.realm_id,
        "realm_name": quest.realm_name,
        "quest_id": quest.quest_id,
        "task_id": quest.task_id,
        "task_title": quest.title,
        "event_type": event_type,
        "champion_user_id": quest.champion_user_id,
        "champion_display_name": quest.champion_display_name,
        "actor_user_id": actor_user_id,
        "actor_name": actor_name,
        "disabled": quest.disabled,
    }
    if extra:
        payload |= extra

    users_to_notify = target_user_ids if target_user_ids is not None else quest.realm_user_ids
    for user_id in users_to_notify:
        hass.bus.async_fire(
            EVENT_NPC_NOTIFICATION,
            {
                **payload,
                "user_id": user_id,
            },
        )
