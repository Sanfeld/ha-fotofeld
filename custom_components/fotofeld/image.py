"""Photos from the library as image entities: On this day, Random, Latest, one per named person, and a Photo frame."""

from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util, slugify

from .api import FotofeldError, FotofeldNotFound
from .button import SIGNAL_NEXT_PHOTOS

SIGNAL_FRAME_SET = "fotofeld_frame_set_{}"          # select -> photo frame: (mode, name)
SIGNAL_FRAME_CHANGED = "fotofeld_frame_changed_{}"  # photo frame -> select
from .const import CONF_PHOTO_MINUTES, CONF_PHOTO_SIZE, DEFAULT_PHOTO_MINUTES, DEFAULT_PHOTO_SIZE, PHOTO_MODES
from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    entities = [
        FotofeldPhoto(hass, entry, "on_this_day", "onthisday"),
        FotofeldPhoto(hass, entry, "random_photo", "random"),
        FotofeldPhoto(hass, entry, "latest_photo", "latest"),
        FotofeldPhoto(hass, entry, "photo_frame", "random"),
    ]
    for person in entry.runtime_data.people:
        entities.append(FotofeldPhoto(hass, entry, f"person_{slugify(person)}", "person", person, translation="person_photo"))
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "next_photo",
        {vol.Optional("mode"): vol.In(PHOTO_MODES), vol.Optional("name"): cv.string},
        "async_next_photo",
    )


class FotofeldPhoto(FotofeldEntity, ImageEntity):
    _attr_content_type = "image/jpeg"

    def __init__(self, hass: HomeAssistant, entry: FotofeldConfigEntry, key: str, mode: str,
                 name: str | None = None, translation: str | None = None) -> None:
        FotofeldEntity.__init__(self, entry, key)
        ImageEntity.__init__(self, hass)
        self._entry = entry
        self._api = entry.runtime_data.api
        self._attr_translation_key = translation or key
        if name:
            self._attr_translation_placeholders = {"person": name}
        self.mode, self.name_filter = mode, name
        self._photo: dict | None = None
        self._bytes: bytes | None = None
        self._size = int(entry.options.get(CONF_PHOTO_SIZE, DEFAULT_PHOTO_SIZE))
        self._minutes = int(entry.options.get(CONF_PHOTO_MINUTES, DEFAULT_PHOTO_MINUTES))
        self._last_day = None
        self._is_frame = key == "photo_frame"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_NEXT_PHOTOS.format(self._entry.entry_id), self._next_from_signal))
        if self._minutes > 0:
            self.async_on_remove(async_track_time_interval(self.hass, self._on_timer, timedelta(minutes=self._minutes)))
        if self._is_frame:
            self.async_on_remove(async_dispatcher_connect(
                self.hass, SIGNAL_FRAME_SET.format(self._entry.entry_id), self._frame_set))
        if self.mode == "onthisday":    # a new day: new memories, even with timed changes off
            self.async_on_remove(async_track_time_interval(self.hass, self._on_day_check, timedelta(minutes=5)))
        self.hass.async_create_task(self._pick())

    @callback
    def _next_from_signal(self) -> None:
        self.hass.async_create_task(self._pick())

    async def _on_timer(self, _now) -> None:
        await self._pick()

    async def _on_day_check(self, _now) -> None:
        if dt_util.now().date() != self._last_day:
            await self._pick()

    @callback
    def _frame_set(self, mode: str, name: str | None) -> None:
        self.hass.async_create_task(self.async_next_photo(mode, name))

    async def async_next_photo(self, mode: str | None = None, name: str | None = None) -> None:
        """Entity action fotofeld.next_photo: a new photo now; mode/name change what this entity shows."""
        if mode:
            self.mode, self.name_filter = mode, name
        elif name:
            self.name_filter = name
        if self._is_frame:
            self._entry.runtime_data.frame = {"mode": self.mode, "name": self.name_filter}
            async_dispatcher_send(self.hass, SIGNAL_FRAME_CHANGED.format(self._entry.entry_id))
        await self._pick()

    async def _pick(self) -> None:
        self._last_day = dt_util.now().date()
        try:
            photo = await self._api.photo(self.mode, self.name_filter)
            data = await self._api.photo_file(photo["id"], self._size)
        except FotofeldNotFound:
            photo, data = None, None
        except FotofeldError as err:
            _LOGGER.debug("No new photo for %s: %s", self.entity_id, err)
            return      # keep showing the last one
        self._photo, self._bytes = photo, data
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return self._bytes

    @property
    def available(self) -> bool:
        return True       # photos stay viewable while the library is busy

    @property
    def extra_state_attributes(self) -> dict:
        p = self._photo or {}
        return {
            "mode": self.mode,
            "filter": self.name_filter,
            "date": p.get("date"),
            "years_ago": p.get("yearsAgo"),
            "people": p.get("people"),
            "subjects": p.get("subjects"),
            "path": p.get("path"),
            "matches": p.get("matches"),
        }
