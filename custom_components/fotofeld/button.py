"""Fotofeld buttons: analyze pictures with Fotofeld Vision, and show new photos on every photo entity."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FotofeldError
from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity

SIGNAL_NEXT_PHOTOS = "fotofeld_next_photos_{}"


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([AnalyzeButton(entry), NextPhotosButton(entry)])


class AnalyzeButton(FotofeldEntity, ButtonEntity):
    _attr_translation_key = "analyze"

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "analyze")
        self._api = entry.runtime_data.api

    async def async_press(self) -> None:
        try:
            await self._api.action("vision")
        except FotofeldError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class NextPhotosButton(FotofeldEntity, ButtonEntity):
    _attr_translation_key = "next_photos"

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "next_photos")
        self._entry_id = entry.entry_id

    async def async_press(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_NEXT_PHOTOS.format(self._entry_id))
