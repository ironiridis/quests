"""Data models for the Quests integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


@dataclass(slots=True)
class Quest:
    """A recurring quest definition."""

    quest_id: str
    realm_id: str
    realm_name: str
    realm_user_ids: list[str]
    task_id: str
    title: str
    interval_days: int = 1
    requires_response: bool = False
    check_limit: int = 0
    check_count: int = 0
    description: str | None = None
    created_at: datetime = field(default_factory=dt_util.utcnow)
    last_completed_at: datetime | None = None
    last_response: str | None = None
    last_completed_by: str | None = None
    deferred_until: datetime | None = None
    champion_user_id: str | None = None
    champion_display_name: str | None = None
    disabled: bool = False

    @property
    def due_at(self) -> datetime:
        """Return when this quest is next due."""
        base = self.last_completed_at or self.created_at
        return base + timedelta(days=max(self.interval_days, 1))

    @property
    def effective_due_at(self) -> datetime:
        """Return the effective due date after deferrals are applied."""
        if self.deferred_until and self.deferred_until > self.due_at:
            return self.deferred_until
        return self.due_at

    def is_due(self, now: datetime | None = None) -> bool:
        """Return whether this quest is currently due."""
        check_time = now or dt_util.utcnow()
        return check_time >= self.effective_due_at

    def is_overdue(self, now: datetime | None = None) -> bool:
        """Return whether this quest is currently overdue."""
        check_time = now or dt_util.utcnow()
        return check_time > self.effective_due_at

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialize quest for storage."""
        return {
            "quest_id": self.quest_id,
            "realm_id": self.realm_id,
            "realm_name": self.realm_name,
            "realm_user_ids": self.realm_user_ids,
            "task_id": self.task_id,
            "title": self.title,
            "interval_days": self.interval_days,
            "requires_response": self.requires_response,
            "check_limit": self.check_limit,
            "check_count": self.check_count,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "last_completed_at": (
                self.last_completed_at.isoformat() if self.last_completed_at else None
            ),
            "last_response": self.last_response,
            "last_completed_by": self.last_completed_by,
            "deferred_until": (
                self.deferred_until.isoformat() if self.deferred_until else None
            ),
            "champion_user_id": self.champion_user_id,
            "champion_display_name": self.champion_display_name,
            "disabled": self.disabled,
        }

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> Quest:
        """Deserialize quest from storage."""
        return cls(
            quest_id=data["quest_id"],
            realm_id=str(data.get("realm_id", "default")),
            realm_name=str(data.get("realm_name", "Default Realm")),
            realm_user_ids=list(data.get("realm_user_ids", [])),
            task_id=str(data.get("task_id", data["quest_id"])),
            title=data["title"],
            interval_days=int(data.get("interval_days", 1)),
            requires_response=bool(data.get("requires_response", False)),
            check_limit=max(int(data.get("check_limit", 0)), 0),
            check_count=max(int(data.get("check_count", 0)), 0),
            description=data.get("description"),
            created_at=_parse_datetime(data.get("created_at")) or dt_util.utcnow(),
            last_completed_at=_parse_datetime(data.get("last_completed_at")),
            last_response=data.get("last_response"),
            last_completed_by=data.get("last_completed_by"),
            deferred_until=_parse_datetime(data.get("deferred_until")),
            champion_user_id=data.get("champion_user_id"),
            champion_display_name=data.get("champion_display_name"),
            disabled=bool(data.get("disabled", False)),
        )


@dataclass(slots=True)
class QuestSummary:
    """A summary of quest status."""

    total_quests: int = 0
    due_quests: int = 0
    overdue_quests: int = 0
    due_requires_response: int = 0
    next_due_at: datetime | None = None
    due_quest_ids: list[str] = field(default_factory=list)
    due_quests_by_realm: dict[str, int] = field(default_factory=dict)
    due_tasks: list[dict[str, str]] = field(default_factory=list)
    realm_names: dict[str, str] = field(default_factory=dict)
    realm_total_counts: dict[str, int] = field(default_factory=dict)
    realm_due_counts: dict[str, int] = field(default_factory=dict)
    realm_overdue_counts: dict[str, int] = field(default_factory=dict)
    realm_requires_response_counts: dict[str, int] = field(default_factory=dict)
    task_champion_names: dict[str, str] = field(default_factory=dict)
    task_champion_user_ids: dict[str, str] = field(default_factory=dict)
    task_due_states: dict[str, bool] = field(default_factory=dict)
    task_next_due_at: dict[str, datetime | None] = field(default_factory=dict)
    task_disabled_states: dict[str, bool] = field(default_factory=dict)
    task_check_limits: dict[str, int] = field(default_factory=dict)
    task_check_counts: dict[str, int] = field(default_factory=dict)
    task_check_allowed: dict[str, bool] = field(default_factory=dict)


def summarize_quests(quests: list[Quest], now: datetime | None = None) -> QuestSummary:
    """Build a summary from all quests."""
    check_time = now or dt_util.utcnow()
    due_quests: list[Quest] = [quest for quest in quests if quest.is_due(check_time)]
    overdue_count = sum(1 for quest in quests if quest.is_overdue(check_time))
    due_requires_response = sum(1 for quest in due_quests if quest.requires_response)
    next_due_at = min((quest.effective_due_at for quest in quests), default=None)

    due_quest_ids: list[str] = []
    due_quests_by_realm: dict[str, int] = {}
    due_tasks: list[dict[str, str]] = []

    realm_names: dict[str, str] = {}
    realm_total_counts: dict[str, int] = {}
    realm_due_counts: dict[str, int] = {}
    realm_overdue_counts: dict[str, int] = {}
    realm_requires_response_counts: dict[str, int] = {}
    task_champion_names: dict[str, str] = {}
    task_champion_user_ids: dict[str, str] = {}
    task_due_states: dict[str, bool] = {}
    task_next_due_at: dict[str, datetime | None] = {}
    task_disabled_states: dict[str, bool] = {}
    task_check_limits: dict[str, int] = {}
    task_check_counts: dict[str, int] = {}
    task_check_allowed: dict[str, bool] = {}

    for quest in quests:
        is_due = False if quest.disabled else quest.is_due(check_time)
        is_overdue = False if quest.disabled else quest.is_overdue(check_time)
        realm_names[quest.realm_id] = quest.realm_name
        realm_total_counts[quest.realm_id] = realm_total_counts.get(quest.realm_id, 0) + 1
        if is_due:
            realm_due_counts[quest.realm_id] = realm_due_counts.get(quest.realm_id, 0) + 1
        if is_overdue:
            realm_overdue_counts[quest.realm_id] = (
                realm_overdue_counts.get(quest.realm_id, 0) + 1
            )
        if is_due and quest.requires_response:
            realm_requires_response_counts[quest.realm_id] = (
                realm_requires_response_counts.get(quest.realm_id, 0) + 1
            )

        task_due_states[quest.quest_id] = is_due
        task_next_due_at[quest.quest_id] = None if quest.disabled else quest.effective_due_at
        task_disabled_states[quest.quest_id] = quest.disabled
        task_check_limits[quest.quest_id] = quest.check_limit
        task_check_counts[quest.quest_id] = quest.check_count
        task_check_allowed[quest.quest_id] = (
            not quest.disabled
            and quest.check_limit > 0
            and quest.check_count < quest.check_limit
        )

        if quest.champion_display_name:
            task_champion_names[quest.quest_id] = quest.champion_display_name
        if quest.champion_user_id:
            task_champion_user_ids[quest.quest_id] = quest.champion_user_id

    for quest in sorted(due_quests, key=lambda item: (item.realm_name, item.title)):
        due_quest_ids.append(quest.quest_id)
        due_quests_by_realm[quest.realm_id] = due_quests_by_realm.get(quest.realm_id, 0) + 1
        due_tasks.append(
            {
                "realm_id": quest.realm_id,
                "realm_name": quest.realm_name,
                "task_id": quest.task_id,
                "title": quest.title,
            }
        )

    return QuestSummary(
        total_quests=len(quests),
        due_quests=len(due_quests),
        overdue_quests=overdue_count,
        due_requires_response=due_requires_response,
        next_due_at=next_due_at,
        due_quest_ids=due_quest_ids,
        due_quests_by_realm=due_quests_by_realm,
        due_tasks=due_tasks,
        realm_names=realm_names,
        realm_total_counts=realm_total_counts,
        realm_due_counts=realm_due_counts,
        realm_overdue_counts=realm_overdue_counts,
        realm_requires_response_counts=realm_requires_response_counts,
        task_champion_names=task_champion_names,
        task_champion_user_ids=task_champion_user_ids,
        task_due_states=task_due_states,
        task_next_due_at=task_next_due_at,
        task_disabled_states=task_disabled_states,
        task_check_limits=task_check_limits,
        task_check_counts=task_check_counts,
        task_check_allowed=task_check_allowed,
    )
