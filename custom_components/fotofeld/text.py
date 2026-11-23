"""Duplicates viewer filter: only originals or duplicates whose path contains this text (2014\\04, a drive name...)."""

from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FotofeldConfigEntry
from .dupviewer import SIGNAL_DUPS
from .entity import FotofeldEntity


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([DupFilter(entry)])


class DupFilter(FotofeldEntity, TextEntity):
    _attr_translation_key = "dup_filter"
    _attr_native_max = 200

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "dup_filter")
        self._entry = entry

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_DUPS.format(self._entry.entry_id), self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        return self._entry.runtime_data.dups.query

    async def async_set_value(self, value: str) -> None:
        await self._entry.runtime_data.dups.set_query(value)
