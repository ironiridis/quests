"""The Quests integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    PLATFORMS,
    QUEST_ID_SEPARATOR,
)
from .coordinator import QuestsCoordinator, QuestsConfigEntry, QuestsRuntimeData
from .models import Quest
from .realms import get_realm_definitions
from .services import async_register_services, async_unregister_services
from .storage import QuestStore


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Set up the Quests integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: QuestsConfigEntry) -> bool:
    """Set up Quests from a config entry."""
    store = QuestStore(hass=hass, entry_id=entry.entry_id)
    await store.async_initialize()
    await _async_sync_store_from_subentries(entry, store)

    coordinator = QuestsCoordinator(hass=hass, store=store)
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    runtime_data = QuestsRuntimeData(coordinator=coordinator, store=store)
    entry.runtime_data = runtime_data
    hass.data[DOMAIN][entry.entry_id] = runtime_data

    first_entry = len(hass.data[DOMAIN]) == 1
    if first_entry:
        async_register_services(hass)

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id)
        if first_entry:
            async_unregister_services(hass)
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QuestsConfigEntry) -> bool:
    """Unload a Quests config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        async_unregister_services(hass)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when it is updated, including realm subentries."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_sync_store_from_subentries(
    entry: QuestsConfigEntry, store: QuestStore
) -> None:
    """Sync realm subentry tasks into persistent quest storage."""
    now = dt_util.utcnow()
    desired_quests: list[Quest] = []

    for realm in get_realm_definitions(entry):
        for task in realm.tasks:
            quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
            desired_quests.append(
                Quest(
                    quest_id=quest_id,
                    realm_id=realm.realm_id,
                    realm_name=realm.realm_name,
                    realm_user_ids=list(realm.owner_user_ids),
                    task_id=task.task_id,
                    title=task.title,
                    description=task.description,
                    interval_days=task.interval_days,
                    requires_response=task.requires_response,
                    check_limit=task.check_limit,
                    created_at=now,
                )
            )

    await store.async_sync_realm_quests(desired_quests)
