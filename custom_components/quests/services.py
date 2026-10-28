"""Service handlers for Quests."""

from __future__ import annotations

from datetime import datetime

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ACTOR,
    ATTR_REALM_ID,
    ATTR_RESPONSE,
    ATTR_TASK_ID,
    DOMAIN,
    QUEST_ID_SEPARATOR,
    SERVICE_CHECK_QUEST,
    SERVICE_COMPLETE_QUEST,
)
from .npc_events import async_fire_task_state_event

COMPLETE_QUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REALM_ID): cv.slug,
        vol.Required(ATTR_TASK_ID): cv.slug,
        vol.Optional(ATTR_RESPONSE): cv.string,
        vol.Optional(ATTR_ACTOR): cv.string,
    }
)

CHECK_QUEST_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_REALM_ID): cv.slug,
        vol.Required(ATTR_TASK_ID): cv.slug,
    }
)


def _get_runtime_data(hass: HomeAssistant):
    """Get runtime data for the loaded Quests entry."""
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        raise ServiceValidationError("Quests is not configured.")
    return next(iter(domain_data.values()))


def _build_quest_id(realm_id: str, task_id: str) -> str:
    """Build a quest ID from realm and task IDs."""
    return f"{realm_id}{QUEST_ID_SEPARATOR}{task_id}"


async def _handle_complete_quest(call: ServiceCall, hass: HomeAssistant) -> None:
    """Mark a quest complete."""
    runtime_data = _get_runtime_data(hass)
    response = call.data.get(ATTR_RESPONSE)
    actor = call.data.get(ATTR_ACTOR)
    completed_at: datetime = dt_util.utcnow()
    quest_id = _build_quest_id(call.data[ATTR_REALM_ID], call.data[ATTR_TASK_ID])

    quest = await runtime_data.store.async_get_quest(quest_id)
    if quest is None:
        raise ServiceValidationError(f"Quest '{quest_id}' does not exist")
    if quest.disabled:
        raise ServiceValidationError(f"Quest '{quest.quest_id}' is disabled.")
    if quest.requires_response and not response:
        raise ServiceValidationError(
            f"Quest '{quest.quest_id}' requires a response when completing."
        )

    try:
        quest = await runtime_data.store.async_complete_quest(
            quest_id=quest_id,
            completed_at=completed_at,
            response=response,
            actor=actor,
        )
    except KeyError as err:
        raise ServiceValidationError(str(err)) from err

    actor_user_id = call.context.user_id
    actor_name = actor
    if actor_name is None and actor_user_id:
        if user := await hass.auth.async_get_user(actor_user_id):
            actor_name = user.name or user.id

    async_fire_task_state_event(
        hass,
        quest,
        event_type="completed",
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        extra={"response": response},
    )

    await runtime_data.coordinator.async_request_refresh()


async def _handle_check_quest(call: ServiceCall, hass: HomeAssistant) -> None:
    """Check a quest, deferring it by 24 hours."""
    runtime_data = _get_runtime_data(hass)
    quest_id = _build_quest_id(call.data[ATTR_REALM_ID], call.data[ATTR_TASK_ID])
    quest = await runtime_data.store.async_get_quest(quest_id)
    if quest is None:
        raise ServiceValidationError(f"Quest '{quest_id}' does not exist")
    if quest.disabled:
        raise ServiceValidationError(f"Quest '{quest.quest_id}' is disabled.")

    try:
        quest = await runtime_data.store.async_check_quest(
            quest_id=quest_id,
            now=dt_util.utcnow(),
        )
    except (KeyError, ValueError) as err:
        raise ServiceValidationError(str(err)) from err

    async_fire_task_state_event(
        hass,
        quest,
        event_type="checked",
        actor_user_id=call.context.user_id,
        extra={"check_count": quest.check_count, "check_limit": quest.check_limit},
    )

    await runtime_data.coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_COMPLETE_QUEST):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_QUEST,
        lambda call: _handle_complete_quest(call, hass),
        schema=COMPLETE_QUEST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_QUEST,
        lambda call: _handle_check_quest(call, hass),
        schema=CHECK_QUEST_SCHEMA,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    for service in (SERVICE_COMPLETE_QUEST, SERVICE_CHECK_QUEST):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
