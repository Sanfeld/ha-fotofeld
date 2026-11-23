"""What the Photo frame shows: Random, On this day, Latest, a person or a subject (from Fotofeld Vision)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity
from .image import SIGNAL_FRAME_CHANGED, SIGNAL_FRAME_SET

FIXED = ["random", "onthisday", "latest"]
PERSON = "Person: "
SUBJECT = "Subject: "


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([FrameSelect(entry)])


class FrameSelect(FotofeldEntity, SelectEntity):
    _attr_translation_key = "frame_shows"

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "frame_shows")
        self._entry = entry
        data = entry.runtime_data
        self._attr_options = FIXED + [PERSON + p for p in data.people] + [SUBJECT + s for s in data.subjects]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_FRAME_CHANGED.format(self._entry.entry_id), self.async_write_ha_state))

    @property
    def current_option(self) -> str | None:
        frame = self._entry.runtime_data.frame
        mode, name = frame["mode"], frame.get("name")
        if mode in FIXED:
            return mode
        option = (PERSON if mode == "person" else SUBJECT) + str(name)
        return option if option in self.options else None

    async def async_select_option(self, option: str) -> None:
        if option.startswith(PERSON):
            mode, name = "person", option[len(PERSON):]
        elif option.startswith(SUBJECT):
            mode, name = "subject", option[len(SUBJECT):]
        else:
            mode, name = option, None
        async_dispatcher_send(self.hass, SIGNAL_FRAME_SET.format(self._entry.entry_id), mode, name)
