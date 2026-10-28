"""Sensor platform for Quests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QUEST_ID_SEPARATOR
from .coordinator import QuestsConfigEntry
from .entity import QuestsEntity
from .models import QuestSummary
from .realms import RealmDefinition, RealmTaskDefinition, get_realm_definitions


@dataclass(frozen=True, kw_only=True)
class RealmMetricDefinition:
    """Definition for a realm summary metric sensor."""

    key: str
    name: str
    icon: str
    value_fn: Callable[[QuestSummary, str], int]


REALM_METRICS: tuple[RealmMetricDefinition, ...] = (
    RealmMetricDefinition(
        key="total_tasks",
        name="Total tasks",
        icon="mdi:map-marker-path",
        value_fn=lambda summary, realm_id: summary.realm_total_counts.get(realm_id, 0),
    ),
    RealmMetricDefinition(
        key="due_tasks",
        name="Due tasks",
        icon="mdi:calendar-alert",
        value_fn=lambda summary, realm_id: summary.realm_due_counts.get(realm_id, 0),
    ),
    RealmMetricDefinition(
        key="overdue_tasks",
        name="Overdue tasks",
        icon="mdi:clock-alert",
        value_fn=lambda summary, realm_id: summary.realm_overdue_counts.get(realm_id, 0),
    ),
    RealmMetricDefinition(
        key="tasks_requiring_response",
        name="Tasks requiring response",
        icon="mdi:message-alert",
        value_fn=lambda summary, realm_id: summary.realm_requires_response_counts.get(
            realm_id, 0
        ),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: QuestsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Quests sensors."""
    for realm in get_realm_definitions(entry):
        entities: list[SensorEntity] = [
            RealmMetricSensor(
                entry=entry,
                realm=realm,
                metric=metric,
            )
            for metric in REALM_METRICS
        ]
        entities.extend(
            TaskChampionSensor(
                entry=entry,
                realm=realm,
                task=task,
            )
            for task in realm.tasks
        )
        entities.extend(
            TaskNextDueSensor(
                entry=entry,
                realm=realm,
                task=task,
            )
            for task in realm.tasks
        )

        async_add_entities(entities, config_subentry_id=realm.subentry_id)


class RealmMetricSensor(QuestsEntity, SensorEntity):
    """Summary sensor for one realm metric."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        metric: RealmMetricDefinition,
    ) -> None:
        """Initialize realm metric sensor."""
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{metric.key}",
        )
        self._realm = realm
        self._metric = metric
        self._attr_name = metric.name
        self._attr_icon = metric.icon
        self._attr_device_info = realm.npc_device_info()

    @property
    @override
    def native_value(self) -> int:
        """Return sensor state."""
        return self._metric.value_fn(self.coordinator.data, self._realm.realm_id)


class TaskChampionSensor(QuestsEntity, SensorEntity):
    """Sensor exposing the champion for one task."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize task champion sensor."""
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_champion",
        )
        self._attr_name = f"{task.title} champion"
        self._attr_icon = "mdi:trophy"
        self._attr_device_info = realm.task_device_info(task)

    @property
    @override
    def native_value(self) -> str:
        """Return the champion display name."""
        return self.coordinator.data.task_champion_names.get(self._quest_id, "Unclaimed")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return champion metadata."""
        champion_user_id = self.coordinator.data.task_champion_user_ids.get(
            self._quest_id
        )
        return {
            "realm_id": self._realm.realm_id,
            "task_id": self._task.task_id,
            "champion_user_id": champion_user_id,
        }


class TaskNextDueSensor(QuestsEntity, SensorEntity):
    """Sensor exposing the next due timestamp for a task."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize next due timestamp sensor."""
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_next_due",
        )
        self._attr_name = f"{task.title} next due"
        self._attr_device_info = realm.task_device_info(task)

    @property
    @override
    def native_value(self) -> datetime | None:
        """Return the fixed next due timestamp until task updates."""
        return self.coordinator.data.task_next_due_at.get(self._quest_id)
