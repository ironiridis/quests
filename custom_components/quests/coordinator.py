"""Data update coordinator for Quests."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .models import QuestSummary, summarize_quests
from .storage import QuestStore

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class QuestsRuntimeData:
    """Runtime data for Quests config entries."""

    coordinator: QuestsCoordinator
    store: QuestStore


type QuestsConfigEntry = ConfigEntry[QuestsRuntimeData]


class QuestsCoordinator(DataUpdateCoordinator[QuestSummary]):
    """Coordinate quest summary updates."""

    def __init__(self, hass: HomeAssistant, store: QuestStore) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            always_update=False,
        )
        self.store = store
        self._known_due_quest_ids: set[str] = set()
        self._initialized_due_tracking = False

    async def _async_update_data(self) -> QuestSummary:
        """Fetch current quest summary."""
        quests = await self.store.async_list_quests()
        summary = summarize_quests(quests)

        current_due_ids = set(summary.due_quest_ids)
        if not self._initialized_due_tracking:
            self._known_due_quest_ids = current_due_ids
            self._initialized_due_tracking = True
            return summary

        newly_due_ids = current_due_ids - self._known_due_quest_ids
        if newly_due_ids:
            from .npc_events import async_fire_task_state_event

            for quest in quests:
                if quest.quest_id in newly_due_ids:
                    async_fire_task_state_event(
                        self.hass,
                        quest,
                        event_type="due",
                    )

        self._known_due_quest_ids = current_due_ids
        return summary
