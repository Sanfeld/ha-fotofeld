"""Diagnostics for Fotofeld (the pairing code is left out)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_CODE
from .coordinator import FotofeldConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: FotofeldConfigEntry) -> dict[str, Any]:
    data = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), {CONF_CODE}),
        "options": dict(entry.options),
        "info": data.info,
        "people": data.people,
        "subjects": data.subjects,
        "stats": data.coordinator.data,
        "last_event_id": data.coordinator.last_event_id,
    }
