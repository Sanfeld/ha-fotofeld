"""Polls the Fotofeld service and turns its events into Home Assistant events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FotofeldApi, FotofeldAuthError, FotofeldError
from .const import (
    CONF_OVERDUE_DAYS,
    DEFAULT_OVERDUE_DAYS,
    DOMAIN,
    EVENT_BUS,
    SCAN_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

type FotofeldConfigEntry = ConfigEntry[FotofeldData]


@dataclass
class FotofeldData:
    """What the platforms share."""

    api: FotofeldApi
    coordinator: FotofeldCoordinator
    info: dict
    people: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    frame: dict = field(default_factory=lambda: {"mode": "random", "name": None})
    dups: object = None      # DuplicateViewer


def parse_time(value: Any) -> datetime | None:
    """Fotofeld sends local times without a zone (the Windows computer's clock)."""
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


class FotofeldCoordinator(DataUpdateCoordinator[dict]):
    """Fetches /api/stats every 30 seconds, and new events with it."""

    config_entry: FotofeldConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FotofeldConfigEntry, api: FotofeldApi) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=timedelta(seconds=SCAN_SECONDS)
        )
        self.api = api
        self.last_event_id: int | None = None
        self.overdue_reported: set[str] = set()
        self._event_listeners: list = []

    @property
    def overdue_days(self) -> int:
        return int(self.config_entry.options.get(CONF_OVERDUE_DAYS, DEFAULT_OVERDUE_DAYS))

    @callback
    def add_event_listener(self, listener) -> callable:
        """The event entity listens here."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    def phone_overdue(self, phone: dict) -> bool:
        last = parse_time(phone.get("lastBackup"))
        if last is None:
            return False      # never backed up through the app (an old folder): nothing to warn about
        return dt_util.now() - last > timedelta(days=self.overdue_days)

    async def _async_update_data(self) -> dict:
        try:
            stats = await self.api.stats()
            first = self.last_event_id is None
            new_events: list[dict] = []
            server_last = int(stats.get("lastEventId") or 0)
            if first or server_last < (self.last_event_id or 0):
                # First poll, or the service restarted: don't replay old events.
                self.last_event_id = server_last
            elif server_last > self.last_event_id:
                got = await self.api.events(self.last_event_id)
                new_events = list(got.get("events") or [])
                self.last_event_id = int(got.get("lastEventId") or server_last)
        except FotofeldAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except FotofeldError as err:
            raise UpdateFailed(str(err)) from err

        for ev in new_events:
            self._fire(str(ev.get("type")), ev.get("data") or {})

        # Phone overdue: reported once per phone until it backs up again.
        for phone in stats.get("phones") or []:
            name = phone.get("name")
            if self.phone_overdue(phone):
                if name not in self.overdue_reported:
                    self.overdue_reported.add(name)
                    if not first:
                        self._fire("phone_overdue", {"phone": name, "lastBackup": phone.get("lastBackup")})
            else:
                self.overdue_reported.discard(name)
        return stats

    @callback
    def _fire(self, event_type: str, data: dict) -> None:
        self.hass.bus.async_fire(EVENT_BUS, {"type": event_type, "entry_id": self.config_entry.entry_id, **data})
        for listener in list(self._event_listeners):
            listener(event_type, data)
