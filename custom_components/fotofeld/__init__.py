"""Fotofeld: the family photo library on a Windows computer, in Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import FotofeldApi, FotofeldAuthError, FotofeldError
from .const import CONF_CODE, CONF_PHOTO_SIZE, DEFAULT_PHOTO_SIZE, DOMAIN, PHOTO_MODES
from .coordinator import FotofeldConfigEntry, FotofeldCoordinator, FotofeldData
from .dupviewer import DuplicateViewer

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

ATTR_CONFIG_ENTRY = "config_entry_id"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Actions: fotofeld.next_photo, fotofeld.analyze, fotofeld.pause, fotofeld.resume, fotofeld.find_photo."""

    def _entries(call: ServiceCall) -> list[FotofeldConfigEntry]:
        wanted = call.data.get(ATTR_CONFIG_ENTRY)
        entries = [e for e in hass.config_entries.async_loaded_entries(DOMAIN) if not wanted or e.entry_id == wanted]
        if not entries:
            raise HomeAssistantError("No Fotofeld is set up")
        return entries

    async def _action(call: ServiceCall, name: str) -> None:
        for entry in _entries(call):
            try:
                await entry.runtime_data.api.action(name)
            except FotofeldError as err:
                raise HomeAssistantError(str(err)) from err
            await entry.runtime_data.coordinator.async_request_refresh()

    async def analyze(call: ServiceCall) -> None:
        await _action(call, "vision")

    async def pause(call: ServiceCall) -> None:
        await _action(call, "pause")

    async def resume(call: ServiceCall) -> None:
        await _action(call, "resume")

    async def find_photo(call: ServiceCall) -> dict:
        entry = _entries(call)[0]
        try:
            return await entry.runtime_data.api.photo(call.data["mode"], call.data.get("name"))
        except FotofeldError as err:
            raise HomeAssistantError(str(err)) from err

    entry_only = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY): cv.string})
    hass.services.async_register(DOMAIN, "analyze", analyze, schema=entry_only)
    hass.services.async_register(DOMAIN, "pause", pause, schema=entry_only)
    hass.services.async_register(DOMAIN, "resume", resume, schema=entry_only)
    hass.services.async_register(
        DOMAIN, "find_photo", find_photo,
        schema=vol.Schema({
            vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
            vol.Required("mode"): vol.In(PHOTO_MODES),
            vol.Optional("name"): cv.string,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    # fotofeld.next_photo is an entity action on the image entities (see image.py).
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry) -> bool:
    api = FotofeldApi(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_CODE])
    try:
        info = await api.info()
    except FotofeldAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except FotofeldError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = FotofeldCoordinator(hass, entry, api)
    entry.runtime_data = FotofeldData(api=api, coordinator=coordinator, info=info)
    try:
        lists = await api.people()
        entry.runtime_data.people = [p["name"] for p in lists.get("people") or []]
        entry.runtime_data.subjects = [s["name"] for s in lists.get("subjects") or []]
    except FotofeldError:
        pass
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data.dups = DuplicateViewer(
        hass, api, entry.entry_id, int(entry.options.get(CONF_PHOTO_SIZE, DEFAULT_PHOTO_SIZE)))
    entry.async_on_unload(entry.runtime_data.dups.shutdown)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: FotofeldConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FotofeldConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
