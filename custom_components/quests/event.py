"""Event platform for Quests."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.event import EventEntity
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_NPC_NOTIFICATION, NPC_EVENT_TYPES
from .coordinator import QuestsConfigEntry
from .realms import RealmDefinition, RealmUser, get_realm_definitions


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: QuestsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Quests NPC event entities."""
    for realm in get_realm_definitions(entry):
        async_add_entities(
            [
                RealmUserNotificationEvent(
                    entry=entry,
                    realm=realm,
                    user=user,
                )
                for user in realm.users
            ],
            config_subentry_id=realm.subentry_id,
        )


class RealmUserNotificationEvent(EventEntity):
    """Event output entity for one realm user."""

    _attr_has_entity_name = True
    _attr_event_types = list(NPC_EVENT_TYPES)
    _attr_should_poll = False

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        user: RealmUser,
    ) -> None:
        """Initialize event entity."""
        self._entry = entry
        self._realm = realm
        self._user = user
        self._attr_unique_id = f"{entry.entry_id}_{realm.realm_id}_notify_{user.user_id}"
        self._attr_name = f"Notify {user.display_name}"
        self._attr_device_info = realm.npc_device_info()

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to NPC event notifications."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_NPC_NOTIFICATION, self._async_handle_event)
        )

    @callback
    def _async_handle_event(self, event: Event) -> None:
        """Handle integration-level task notification events."""
        if event.data.get("realm_id") != self._realm.realm_id:
            return
        if event.data.get("user_id") != self._user.user_id:
            return

        event_type = event.data.get("event_type")
        if event_type not in self.event_types:
            return

        attributes: dict[str, Any] = {
            key: value for key, value in event.data.items() if key != "event_type"
        }
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
