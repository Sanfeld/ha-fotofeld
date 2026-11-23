"""Pause the Fotofeld service (no USB, inbox or phone work) from Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FotofeldError
from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([PausedSwitch(entry)])


class PausedSwitch(FotofeldEntity, SwitchEntity):
    _attr_translation_key = "paused"

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "paused")
        self._api = entry.runtime_data.api

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("paused"))

    async def _set(self, action: str) -> None:
        try:
            await self._api.action(action)
        except FotofeldError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set("pause")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set("resume")
