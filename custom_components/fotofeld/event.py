"""One event entity that shows what Fotofeld did last (USB imports, disk problems, Vision, phones)."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_TYPES
from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([FotofeldEvent(entry)])


class FotofeldEvent(FotofeldEntity, EventEntity):
    _attr_translation_key = "activity_event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "events")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.add_event_listener(self._on_event))

    @callback
    def _on_event(self, event_type: str, data: dict) -> None:
        if event_type in EVENT_TYPES:
            self._trigger_event(event_type, data)
            self.async_write_ha_state()
