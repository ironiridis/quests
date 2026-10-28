"""Binary sensor platform for Quests."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QUEST_ID_SEPARATOR
from .coordinator import QuestsConfigEntry
from .entity import QuestsEntity
from .realms import RealmDefinition, RealmTaskDefinition, get_realm_definitions


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: QuestsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Quests binary sensors."""
    for realm in get_realm_definitions(entry):
        async_add_entities(
            [
                TaskDueBinarySensor(
                    entry=entry,
                    realm=realm,
                    task=task,
                )
                for task in realm.tasks
            ],
            config_subentry_id=realm.subentry_id,
        )


class TaskDueBinarySensor(QuestsEntity, BinarySensorEntity):
    """Binary sensor that is true when a task is due."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_icon = "mdi:calendar-alert"

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize task due binary sensor."""
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_due",
        )
        self._attr_name = f"{task.title} due"
        self._attr_device_info = realm.task_device_info(task)

    @property
    @override
    def is_on(self) -> bool:
        """Return whether task is currently due."""
        return self.coordinator.data.task_due_states.get(self._quest_id, False)
