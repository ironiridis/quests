"""Switch platform for Quests."""

from __future__ import annotations

from typing import override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QUEST_ID_SEPARATOR
from .coordinator import QuestsConfigEntry
from .entity import QuestsEntity
from .npc_events import async_fire_task_state_event
from .realms import RealmDefinition, RealmTaskDefinition, get_realm_definitions


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: QuestsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Quests task disable switches."""
    for realm in get_realm_definitions(entry):
        async_add_entities(
            [
                TaskDisabledSwitch(
                    entry=entry,
                    realm=realm,
                    task=task,
                )
                for task in realm.tasks
            ],
            config_subentry_id=realm.subentry_id,
        )


class TaskDisabledSwitch(QuestsEntity, SwitchEntity):
    """Switch that disables/enables a task."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:toggle-switch-off-outline"

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize task disable switch."""
        self._entry = entry
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_disabled",
        )
        self._attr_name = f"{task.title} disabled"
        self._attr_device_info = realm.task_device_info(task)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the task is disabled."""
        return self.coordinator.data.task_disabled_states.get(self._quest_id, False)

    @override
    async def async_turn_on(self, **kwargs) -> None:
        """Disable the task."""
        await self._async_set_disabled_state(True)

    @override
    async def async_turn_off(self, **kwargs) -> None:
        """Enable the task."""
        await self._async_set_disabled_state(False)

    async def _async_set_disabled_state(self, disabled: bool) -> None:
        """Set disabled state and fire side effects."""
        runtime_data = self._entry.runtime_data
        quest, changed = await runtime_data.store.async_set_disabled(
            self._quest_id, disabled=disabled
        )

        if changed and disabled and quest.champion_user_id:
            actor_user_id = self._context.user_id if self._context else None
            actor_name: str | None = None
            if actor_user_id and (user := await self.hass.auth.async_get_user(actor_user_id)):
                actor_name = user.name or user.id

            async_fire_task_state_event(
                self.hass,
                quest,
                event_type="disabled",
                actor_user_id=actor_user_id,
                actor_name=actor_name,
                target_user_ids=[quest.champion_user_id],
            )

        await runtime_data.coordinator.async_request_refresh()
