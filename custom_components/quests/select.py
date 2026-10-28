"""Select platform for Quests."""

from __future__ import annotations

from collections import Counter
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import QUEST_ID_SEPARATOR
from .coordinator import QuestsConfigEntry
from .entity import QuestsEntity
from .npc_events import async_fire_task_state_event
from .realms import RealmDefinition, RealmTaskDefinition, get_realm_definitions

UNCLAIMED_OPTION = "Unclaimed"


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: QuestsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Quests champion selectors."""
    for realm in get_realm_definitions(entry):
        async_add_entities(
            [
                TaskChampionSelect(
                    entry=entry,
                    realm=realm,
                    task=task,
                )
                for task in realm.tasks
            ],
            config_subentry_id=realm.subentry_id,
        )


class TaskChampionSelect(QuestsEntity, SelectEntity):
    """Selector for directly setting a task champion."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-check"

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize champion selector."""
        self._entry = entry
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_champion_select",
        )
        self._attr_name = f"{task.title} champion"
        self._attr_device_info = realm.task_device_info(task)

        self._option_to_user_id = _build_option_map(realm)
        self._user_id_to_option = {
            user_id: option for option, user_id in self._option_to_user_id.items()
        }
        self._user_id_to_display_name = {
            user.user_id: user.display_name for user in realm.users
        }
        self._attr_options = [UNCLAIMED_OPTION, *self._option_to_user_id]

    @property
    @override
    def available(self) -> bool:
        """Return whether selector is available."""
        return super().available and not self.coordinator.data.task_disabled_states.get(
            self._quest_id, False
        )

    @property
    @override
    def current_option(self) -> str:
        """Return the selected champion option."""
        champion_user_id = self.coordinator.data.task_champion_user_ids.get(self._quest_id)
        if champion_user_id is None:
            return UNCLAIMED_OPTION
        return self._user_id_to_option.get(champion_user_id, UNCLAIMED_OPTION)

    @override
    async def async_select_option(self, option: str) -> None:
        """Assign or clear champion."""
        if option not in self.options:
            raise HomeAssistantError(f"Invalid champion option '{option}'.")

        runtime_data = self._entry.runtime_data
        quest = await runtime_data.store.async_get_quest(self._quest_id)
        if quest is None:
            raise HomeAssistantError(f"Quest '{self._quest_id}' does not exist.")
        if quest.disabled:
            raise HomeAssistantError(f"Quest '{self._quest_id}' is disabled.")

        champion_user_id: str | None
        champion_display_name: str | None
        if option == UNCLAIMED_OPTION:
            champion_user_id = None
            champion_display_name = None
        else:
            champion_user_id = self._option_to_user_id[option]
            champion_display_name = self._user_id_to_display_name.get(
                champion_user_id, option
            )

        quest = await runtime_data.store.async_set_champion(
            self._quest_id,
            champion_user_id=champion_user_id,
            champion_display_name=champion_display_name,
        )

        actor_user_id = self._context.user_id if self._context else None
        actor_name: str | None = None
        if actor_user_id and (user := await self.hass.auth.async_get_user(actor_user_id)):
            actor_name = user.name or user.id

        async_fire_task_state_event(
            self.hass,
            quest,
            event_type="assigned",
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            extra={
                "champion_user_id": champion_user_id,
                "champion_display_name": champion_display_name,
            },
        )
        await runtime_data.coordinator.async_request_refresh()


def _build_option_map(realm: RealmDefinition) -> dict[str, str]:
    """Build unique display options mapped to user IDs."""
    name_counts = Counter(user.display_name for user in realm.users)
    option_map: dict[str, str] = {}
    for user in realm.users:
        label = user.display_name
        if name_counts[label] > 1:
            label = f"{label} ({user.user_id[:8]})"
        option_map[label] = user.user_id
    return option_map
