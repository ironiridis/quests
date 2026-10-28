"""Helpers for realm subentry parsing and device metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    ATTR_CHECK_LIMIT,
    ATTR_DESCRIPTION,
    ATTR_INTERVAL_DAYS,
    ATTR_REQUIRES_RESPONSE,
    ATTR_TITLE,
    DOMAIN,
    SUBENTRY_FIELD_REALM_ID,
    SUBENTRY_FIELD_REALM_USERS,
    SUBENTRY_FIELD_TASK_ID,
    SUBENTRY_FIELD_TASKS,
    SUBENTRY_FIELD_USER_ID,
    SUBENTRY_FIELD_USER_NAME,
    SUBENTRY_REALM,
)


@dataclass(slots=True, frozen=True)
class RealmUser:
    """A realm-enrolled user."""

    user_id: str
    display_name: str


@dataclass(slots=True, frozen=True)
class RealmTaskDefinition:
    """Task definition configured in a realm."""

    task_id: str
    title: str
    description: str | None
    interval_days: int
    requires_response: bool
    check_limit: int


@dataclass(slots=True, frozen=True)
class RealmDefinition:
    """Parsed realm definition from a config subentry."""

    subentry_id: str
    realm_id: str
    realm_name: str
    users: tuple[RealmUser, ...]
    tasks: tuple[RealmTaskDefinition, ...]

    @property
    def owner_user_ids(self) -> tuple[str, ...]:
        """Return enrolled user IDs."""
        return tuple(user.user_id for user in self.users)

    def npc_device_info(self) -> DeviceInfo:
        """Return NPC device metadata for the realm."""
        return DeviceInfo(
            identifiers={self.npc_device_identifier},
            name=f"{self.realm_name} NPC",
            manufacturer="Quests",
            model="Realm NPC",
        )

    @property
    def npc_device_identifier(self) -> tuple[str, str]:
        """Return the device identifier tuple for the realm NPC."""
        return (DOMAIN, f"npc_{self.realm_id}")

    def task_device_info(self, task: RealmTaskDefinition) -> DeviceInfo:
        """Return task device metadata."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"task_{self.realm_id}_{task.task_id}")},
            name=task.title,
            manufacturer="Quests",
            model="Realm Task",
            via_device=self.npc_device_identifier,
        )


def get_realm_definitions(entry: ConfigEntry) -> list[RealmDefinition]:
    """Parse realm definitions from a config entry."""
    realms: list[RealmDefinition] = []

    for subentry in entry.get_subentries_of_type(SUBENTRY_REALM):
        realm_id = str(
            subentry.data.get(SUBENTRY_FIELD_REALM_ID)
            or subentry.unique_id
            or subentry.subentry_id
        )
        realm_name = subentry.title

        users = _parse_realm_users(subentry.data)
        tasks = _parse_realm_tasks(subentry.data)

        realms.append(
            RealmDefinition(
                subentry_id=subentry.subentry_id,
                realm_id=realm_id,
                realm_name=realm_name,
                users=tuple(users),
                tasks=tuple(tasks),
            )
        )

    return realms


def _parse_realm_users(data: dict[str, Any]) -> list[RealmUser]:
    """Parse realm users from subentry data."""
    users: list[RealmUser] = []
    for user in data.get(SUBENTRY_FIELD_REALM_USERS, []):
        user_id = str(user.get(SUBENTRY_FIELD_USER_ID, "")).strip()
        if not user_id:
            continue
        display_name = str(user.get(SUBENTRY_FIELD_USER_NAME, user_id)).strip()
        users.append(RealmUser(user_id=user_id, display_name=display_name))
    return users


def _parse_realm_tasks(data: dict[str, Any]) -> list[RealmTaskDefinition]:
    """Parse realm tasks from subentry data."""
    parsed: list[RealmTaskDefinition] = []
    for raw_task in data.get(SUBENTRY_FIELD_TASKS, []):
        task_id = str(raw_task.get(SUBENTRY_FIELD_TASK_ID, "")).strip()
        title = str(raw_task.get(ATTR_TITLE, "")).strip()
        if not task_id or not title:
            continue

        parsed.append(
            RealmTaskDefinition(
                task_id=task_id,
                title=title,
                description=(
                    str(raw_task[ATTR_DESCRIPTION]).strip()
                    if raw_task.get(ATTR_DESCRIPTION)
                    else None
                ),
                interval_days=max(int(raw_task.get(ATTR_INTERVAL_DAYS, 1)), 1),
                requires_response=bool(raw_task.get(ATTR_REQUIRES_RESPONSE, False)),
                check_limit=max(int(raw_task.get(ATTR_CHECK_LIMIT, 0)), 0),
            )
        )

    return parsed
