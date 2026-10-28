"""Storage helpers for the Quests integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_PREFIX, STORAGE_VERSION
from .models import Quest

_LOGGER = logging.getLogger(__name__)


class QuestStore:
    """Persist and mutate quest data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize quest storage."""
        self._store = Store[dict[str, Any]](
            hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}_{entry_id}"
        )
        self._lock = asyncio.Lock()
        self._quests: dict[str, Quest] = {}

    async def async_initialize(self) -> None:
        """Load quest data from persistent storage."""
        data = await self._store.async_load()
        if data is None:
            self._quests = {}
            return

        try:
            quests = [Quest.from_storage_dict(item) for item in data.get("quests", [])]
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.error("Failed to load quests storage data: %s", err)
            raise HomeAssistantError("Failed to load quests storage data") from err

        self._quests = {quest.quest_id: quest for quest in quests}

    async def async_list_quests(self) -> list[Quest]:
        """Return all quests."""
        async with self._lock:
            return list(self._quests.values())

    async def async_get_quest(self, quest_id: str) -> Quest | None:
        """Return a quest by id."""
        async with self._lock:
            return self._quests.get(quest_id)

    async def async_sync_realm_quests(self, quests: list[Quest]) -> None:
        """Replace the managed quest set from realm definitions."""
        async with self._lock:
            synced_quests: dict[str, Quest] = {}
            for quest in quests:
                if existing := self._quests.get(quest.quest_id):
                    quest.created_at = existing.created_at
                    quest.last_completed_at = existing.last_completed_at
                    quest.last_response = existing.last_response
                    quest.last_completed_by = existing.last_completed_by
                    quest.deferred_until = existing.deferred_until
                    quest.champion_user_id = existing.champion_user_id
                    quest.champion_display_name = existing.champion_display_name
                    quest.disabled = existing.disabled
                    quest.check_count = min(existing.check_count, quest.check_limit)
                synced_quests[quest.quest_id] = quest

            self._quests = synced_quests
            await self._async_save_locked()

    async def async_complete_quest(
        self,
        quest_id: str,
        *,
        completed_at: datetime,
        response: str | None,
        actor: str | None,
    ) -> Quest:
        """Mark a quest as complete."""
        async with self._lock:
            if quest_id not in self._quests:
                raise KeyError(f"Quest '{quest_id}' does not exist")

            quest = self._quests[quest_id]
            quest.last_completed_at = completed_at
            quest.last_response = response
            quest.last_completed_by = actor
            quest.deferred_until = None
            quest.check_count = 0
            await self._async_save_locked()

            return quest

    async def async_claim_quest(
        self,
        quest_id: str,
        *,
        champion_user_id: str,
        champion_display_name: str,
    ) -> Quest:
        """Claim a quest for a user."""
        async with self._lock:
            if quest_id not in self._quests:
                raise KeyError(f"Quest '{quest_id}' does not exist")

            quest = self._quests[quest_id]
            quest.champion_user_id = champion_user_id
            quest.champion_display_name = champion_display_name
            await self._async_save_locked()

            return quest

    async def async_set_disabled(
        self, quest_id: str, *, disabled: bool
    ) -> tuple[Quest, bool]:
        """Set disabled state for a quest and return (quest, changed)."""
        async with self._lock:
            if quest_id not in self._quests:
                raise KeyError(f"Quest '{quest_id}' does not exist")

            quest = self._quests[quest_id]
            changed = quest.disabled != disabled
            if changed:
                quest.disabled = disabled
                await self._async_save_locked()

            return quest, changed

    async def async_check_quest(self, quest_id: str, *, now: datetime) -> Quest:
        """Check a quest, deferring it by 24 hours if checks remain."""
        async with self._lock:
            if quest_id not in self._quests:
                raise KeyError(f"Quest '{quest_id}' does not exist")

            quest = self._quests[quest_id]
            if quest.check_limit < 1:
                raise ValueError(f"Quest '{quest_id}' is not checkable")
            if quest.check_count >= quest.check_limit:
                raise ValueError(
                    f"Quest '{quest_id}' has reached its check limit "
                    f"({quest.check_limit})"
                )

            quest.check_count += 1
            quest.deferred_until = now + timedelta(hours=24)
            await self._async_save_locked()

            return quest

    async def _async_save_locked(self) -> None:
        """Save storage while lock is held."""
        await self._store.async_save(
            {
                "quests": [
                    self._quests[quest_id].to_storage_dict()
                    for quest_id in sorted(self._quests)
                ]
            }
        )
