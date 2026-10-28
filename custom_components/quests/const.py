"""Constants for the Quests integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "quests"

DEFAULT_NAME = "Quests"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_data"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.EVENT,
]

SERVICE_COMPLETE_QUEST = "complete_quest"
SERVICE_CHECK_QUEST = "check_quest"

SUBENTRY_REALM = "realm"
SUBENTRY_FIELD_TASKS = "tasks"
SUBENTRY_FIELD_TASK_ID = "task_id"
SUBENTRY_FIELD_REALM_ID = "realm_id"
SUBENTRY_FIELD_REALM_USERS = "realm_users"
SUBENTRY_FIELD_USER_ID = "user_id"
SUBENTRY_FIELD_USER_NAME = "display_name"
SUBENTRY_FIELD_OWNER_USER_IDS = "owner_user_ids"

QUEST_ID_SEPARATOR = "__"
EVENT_NPC_NOTIFICATION = f"{DOMAIN}_npc_notification"
NPC_EVENT_TYPES: tuple[str, ...] = ("assigned", "due", "completed", "checked", "disabled")

ATTR_REALM_ID = "realm_id"
ATTR_TASK_ID = "task_id"
ATTR_TITLE = "title"
ATTR_DESCRIPTION = "description"
ATTR_INTERVAL_DAYS = "interval_days"
ATTR_REQUIRES_RESPONSE = "requires_response"
ATTR_CHECK_LIMIT = "check_limit"
ATTR_RESPONSE = "response"
ATTR_ACTOR = "actor"
