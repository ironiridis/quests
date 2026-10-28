"""Button platform for Quests."""

from __future__ import annotations

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

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
    """Set up Quests task action buttons."""
    for realm in get_realm_definitions(entry):
        entities: list[ButtonEntity] = []
        for task in realm.tasks:
            entities.append(QuestClaimButton(entry=entry, realm=realm, task=task))
            entities.append(QuestCompleteButton(entry=entry, realm=realm, task=task))
            if task.check_limit > 0:
                entities.append(QuestCheckButton(entry=entry, realm=realm, task=task))

        async_add_entities(entities, config_subentry_id=realm.subentry_id)


class TaskActionButton(QuestsEntity, ButtonEntity):
    """Base class for task action buttons."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
        unique_suffix: str,
        name_suffix: str,
        icon: str,
    ) -> None:
        """Initialize button."""
        self._entry = entry
        self._realm = realm
        self._task = task
        self._quest_id = f"{realm.realm_id}{QUEST_ID_SEPARATOR}{task.task_id}"
        super().__init__(
            coordinator=entry.runtime_data.coordinator,
            entry_id=entry.entry_id,
            unique_key=f"{realm.realm_id}_{task.task_id}_{unique_suffix}",
        )
        self._attr_name = f"{task.title} {name_suffix}"
        self._attr_icon = icon
        self._attr_device_info = realm.task_device_info(task)

    @property
    def _is_disabled(self) -> bool:
        """Return whether the task is disabled."""
        return self.coordinator.data.task_disabled_states.get(self._quest_id, False)

    async def _async_actor(self) -> tuple[str | None, str | None]:
        """Return (actor_user_id, actor_name) from context."""
        actor_user_id = self._context.user_id if self._context else None
        actor_name: str | None = None
        if actor_user_id and (user := await self.hass.auth.async_get_user(actor_user_id)):
            actor_name = user.name or user.id
        return actor_user_id, actor_name


class QuestClaimButton(TaskActionButton):
    """Button used to claim a quest."""

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize claim button."""
        super().__init__(
            entry=entry,
            realm=realm,
            task=task,
            unique_suffix="claim_button",
            name_suffix="claim",
            icon="mdi:flag-checkered",
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether this button is available."""
        return super().available and not self._is_disabled

    @override
    async def async_press(self) -> None:
        """Claim the quest for the user who pressed the button."""
        if self._context is None or self._context.user_id is None:
            raise HomeAssistantError("Claiming a quest requires an authenticated user.")

        runtime_data = self._entry.runtime_data
        user_id = self._context.user_id
        if (user := await self.hass.auth.async_get_user(user_id)) is None:
            raise HomeAssistantError("Unable to identify the user who claimed the quest.")
        display_name = user.name or user.id

        quest = await runtime_data.store.async_get_quest(self._quest_id)
        if quest is None:
            raise HomeAssistantError(f"Quest '{self._quest_id}' does not exist.")
        if quest.disabled:
            raise HomeAssistantError(f"Quest '{self._quest_id}' is disabled.")
        if user_id not in quest.realm_user_ids:
            raise HomeAssistantError(
                f"User '{display_name}' is not enrolled in realm '{self._realm.realm_name}'."
            )

        quest = await runtime_data.store.async_claim_quest(
            self._quest_id,
            champion_user_id=user_id,
            champion_display_name=display_name,
        )
        async_fire_task_state_event(
            self.hass,
            quest,
            event_type="assigned",
            actor_user_id=user_id,
            actor_name=display_name,
        )
        await runtime_data.coordinator.async_request_refresh()


class QuestCompleteButton(TaskActionButton):
    """Button used to complete a quest."""

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize complete button."""
        super().__init__(
            entry=entry,
            realm=realm,
            task=task,
            unique_suffix="complete_button",
            name_suffix="complete",
            icon="mdi:check-bold",
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether this button is available."""
        return super().available and not self._is_disabled

    @override
    async def async_press(self) -> None:
        """Complete the task."""
        runtime_data = self._entry.runtime_data
        quest = await runtime_data.store.async_get_quest(self._quest_id)
        if quest is None:
            raise HomeAssistantError(f"Quest '{self._quest_id}' does not exist.")
        if quest.disabled:
            raise HomeAssistantError(f"Quest '{self._quest_id}' is disabled.")

        actor_user_id, actor_name = await self._async_actor()
        response = (
            f"Completed via button by {actor_name or actor_user_id or 'unknown'}"
            if quest.requires_response
            else None
        )
        quest = await runtime_data.store.async_complete_quest(
            quest_id=self._quest_id,
            completed_at=dt_util.utcnow(),
            response=response,
            actor=actor_name,
        )
        async_fire_task_state_event(
            self.hass,
            quest,
            event_type="completed",
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            extra={"response": response},
        )
        await runtime_data.coordinator.async_request_refresh()


class QuestCheckButton(TaskActionButton):
    """Button used to check a quest and defer it for 24h."""

    def __init__(
        self,
        *,
        entry: QuestsConfigEntry,
        realm: RealmDefinition,
        task: RealmTaskDefinition,
    ) -> None:
        """Initialize check button."""
        super().__init__(
            entry=entry,
            realm=realm,
            task=task,
            unique_suffix="check_button",
            name_suffix="check",
            icon="mdi:timer-sand",
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether this button is available."""
        return super().available and self.coordinator.data.task_check_allowed.get(
            self._quest_id, False
        )

    @override
    async def async_press(self) -> None:
        """Check the task."""
        runtime_data = self._entry.runtime_data
        quest = await runtime_data.store.async_get_quest(self._quest_id)
        if quest is None:
            raise HomeAssistantError(f"Quest '{self._quest_id}' does not exist.")
        if quest.disabled:
            raise HomeAssistantError(f"Quest '{self._quest_id}' is disabled.")

        try:
            quest = await runtime_data.store.async_check_quest(
                self._quest_id,
                now=dt_util.utcnow(),
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        actor_user_id, actor_name = await self._async_actor()
        async_fire_task_state_event(
            self.hass,
            quest,
            event_type="checked",
            actor_user_id=actor_user_id,
            actor_name=actor_name,
            extra={"check_count": quest.check_count, "check_limit": quest.check_limit},
        )
        await runtime_data.coordinator.async_request_refresh()
