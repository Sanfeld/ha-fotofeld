"""Set up Fotofeld: address of the Fotofeld computer and its pairing code (shown in section 5 of the window)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import FotofeldApi, FotofeldAuthError, FotofeldError
from .const import (
    CONF_CODE,
    CONF_OVERDUE_DAYS,
    CONF_PHOTO_MINUTES,
    CONF_PHOTO_SIZE,
    DEFAULT_OVERDUE_DAYS,
    DEFAULT_PHOTO_MINUTES,
    DEFAULT_PHOTO_SIZE,
    DEFAULT_PORT,
    DOMAIN,
)


class FotofeldConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fotofeld config flow."""

    VERSION = 1

    async def _check(self, host: str, port: int, code: str) -> tuple[dict | None, str | None]:
        api = FotofeldApi(async_get_clientsession(self.hass), host, port, code)
        try:
            info = await api.info()
        except FotofeldAuthError:
            return None, "invalid_auth"
        except FotofeldError:
            return None, "cannot_connect"
        if info.get("name") != "Fotofeld" or int(info.get("api", 0)) < 2:
            return None, "old_version"
        return info, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            info, error = await self._check(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_CODE])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(str(info["server"]).lower())
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]})
                return self.async_create_entry(title=f"Fotofeld {info['server']}", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_CODE): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            _, error = await self._check(entry.data[CONF_HOST], entry.data[CONF_PORT], user_input[CONF_CODE])
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_CODE: user_input[CONF_CODE]})
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_CODE): str}), errors=errors
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            info, error = await self._check(user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_CODE])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(str(info["server"]).lower())
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
            vol.Required(CONF_PORT, default=entry.data[CONF_PORT]): int,
            vol.Required(CONF_CODE, default=entry.data[CONF_CODE]): str,
        })
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> FotofeldOptionsFlow:
        return FotofeldOptionsFlow()


class FotofeldOptionsFlow(OptionsFlow):
    """How often photos change, their size, and when a phone counts as overdue."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        o = self.config_entry.options
        num = lambda lo, hi, unit: selector.NumberSelector(  # noqa: E731
            selector.NumberSelectorConfig(min=lo, max=hi, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement=unit)
        )
        schema = vol.Schema({
            vol.Required(CONF_PHOTO_MINUTES, default=o.get(CONF_PHOTO_MINUTES, DEFAULT_PHOTO_MINUTES)): num(0, 1440, "min"),
            vol.Required(CONF_PHOTO_SIZE, default=o.get(CONF_PHOTO_SIZE, DEFAULT_PHOTO_SIZE)): num(320, 4096, "px"),
            vol.Required(CONF_OVERDUE_DAYS, default=o.get(CONF_OVERDUE_DAYS, DEFAULT_OVERDUE_DAYS)): num(1, 90, "d"),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
