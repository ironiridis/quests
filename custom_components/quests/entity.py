"""Base entity for Quests."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import QuestsCoordinator


class QuestsEntity(CoordinatorEntity[QuestsCoordinator]):
    """Base class for Quests entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: QuestsCoordinator, entry_id: str, unique_key: str
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{unique_key}"
