"""Config flow for Quests."""

from __future__ import annotations

from typing import Any, override

from probatio import Required, Schema

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    ATTR_CHECK_LIMIT,
    ATTR_DESCRIPTION,
    ATTR_INTERVAL_DAYS,
    ATTR_REQUIRES_RESPONSE,
    ATTR_TITLE,
    DEFAULT_NAME,
    DOMAIN,
    SUBENTRY_FIELD_OWNER_USER_IDS,
    SUBENTRY_FIELD_REALM_ID,
    SUBENTRY_FIELD_REALM_USERS,
    SUBENTRY_FIELD_TASK_ID,
    SUBENTRY_FIELD_TASKS,
    SUBENTRY_FIELD_USER_ID,
    SUBENTRY_FIELD_USER_NAME,
    SUBENTRY_REALM,
)

REALM_TASK_SCHEMA = Schema(
    {
        Required(ATTR_TITLE): str,
        Required(ATTR_DESCRIPTION, default=""): str,
        Required(ATTR_INTERVAL_DAYS, default=1): int,
        Required(ATTR_REQUIRES_RESPONSE, default=False): bool,
        Required(ATTR_CHECK_LIMIT, default=0): int,
        Required("add_another", default=False): bool,
    }
)


class QuestsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Quests."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, _config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        return {SUBENTRY_REALM: RealmSubentryFlow}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=DEFAULT_NAME, data={})

        return self.async_show_form(step_id="user")


class RealmSubentryFlow(ConfigSubentryFlow):
    """Handle subentry flows for realms."""

    def __init__(self) -> None:
        """Initialize realm subentry flow."""
        self._realm_name: str = ""
        self._realm_id: str = ""
        self._realm_users: list[dict[str, str]] = []
        self._tasks: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure realm name and enrolled users."""
        errors: dict[str, str] = {}
        user_options = await self._async_user_options()
        if not user_options:
            return self.async_abort(reason="no_available_users")
        data_schema = _build_realm_user_schema(user_options)

        if user_input is not None:
            realm_name = user_input[CONF_NAME].strip()
            realm_id = slugify(realm_name)
            selected_user_ids = user_input[SUBENTRY_FIELD_OWNER_USER_IDS]

            if not realm_id:
                errors["base"] = "invalid_realm_name"
            elif self._realm_exists(realm_id):
                return self.async_abort(reason="realm_already_configured")
            elif not selected_user_ids:
                errors["base"] = "no_realm_users"
            else:
                self._realm_name = realm_name
                self._realm_id = realm_id
                self._realm_users = _build_realm_users_from_selection(
                    selected_user_ids, user_options
                )
                self._tasks = []
                return await self.async_step_task()

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_task(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add one repeating task to this realm."""
        errors: dict[str, str] = {}

        if user_input is not None:
            title = user_input[ATTR_TITLE].strip()
            task_id = slugify(title)
            interval_days = user_input[ATTR_INTERVAL_DAYS]

            if not task_id:
                errors["base"] = "invalid_task_name"
            elif interval_days < 1:
                errors["base"] = "invalid_interval"
            elif user_input[ATTR_CHECK_LIMIT] < 0:
                errors["base"] = "invalid_check_limit"
            elif any(task[SUBENTRY_FIELD_TASK_ID] == task_id for task in self._tasks):
                errors["base"] = "duplicate_task"
            else:
                self._tasks.append(
                    {
                        SUBENTRY_FIELD_TASK_ID: task_id,
                        ATTR_TITLE: title,
                        ATTR_DESCRIPTION: user_input[ATTR_DESCRIPTION].strip() or None,
                        ATTR_INTERVAL_DAYS: interval_days,
                        ATTR_REQUIRES_RESPONSE: user_input[ATTR_REQUIRES_RESPONSE],
                        ATTR_CHECK_LIMIT: user_input[ATTR_CHECK_LIMIT],
                    }
                )

                if user_input["add_another"]:
                    return self.async_show_form(
                        step_id="task", data_schema=REALM_TASK_SCHEMA
                    )

                return self.async_create_entry(
                    title=self._realm_name,
                    unique_id=self._realm_id,
                    data={
                        SUBENTRY_FIELD_REALM_ID: self._realm_id,
                        SUBENTRY_FIELD_REALM_USERS: self._realm_users,
                        SUBENTRY_FIELD_TASKS: self._tasks,
                    },
                )

        return self.async_show_form(
            step_id="task",
            data_schema=REALM_TASK_SCHEMA,
            errors=errors,
        )

    async def _async_user_options(self) -> list[dict[str, str]]:
        """Build user selector options from active Home Assistant users."""
        users = await self.hass.auth.async_get_users()
        options: list[dict[str, str]] = []
        for user in users:
            if not user.is_active or user.system_generated:
                continue
            display_name = user.name or user.id
            options.append({"value": user.id, "label": display_name})

        options.sort(key=lambda option: option["label"].lower())
        return options

    def _realm_exists(self, realm_id: str) -> bool:
        """Return whether the realm already exists on the parent entry."""
        entry = self._get_entry()
        return any(
            subentry.unique_id == realm_id
            for subentry in entry.get_subentries_of_type(SUBENTRY_REALM)
        )


def _build_realm_user_schema(user_options: list[dict[str, str]]) -> Schema:
    """Build realm setup schema with dynamic user selection."""
    return Schema(
        {
            Required(CONF_NAME): str,
            Required(SUBENTRY_FIELD_OWNER_USER_IDS, default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=user_options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _build_realm_users_from_selection(
    selected_user_ids: list[str], user_options: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Build stored realm user entries from user IDs."""
    labels_by_user_id = {
        option["value"]: option["label"]
        for option in user_options
        if "value" in option and "label" in option
    }
    return [
        {
            SUBENTRY_FIELD_USER_ID: user_id,
            SUBENTRY_FIELD_USER_NAME: labels_by_user_id.get(user_id, user_id),
        }
        for user_id in selected_user_ids
    ]
