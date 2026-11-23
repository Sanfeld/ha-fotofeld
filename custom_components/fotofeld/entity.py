"""Base entity: everything belongs to one Fotofeld device per server."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FotofeldConfigEntry, FotofeldCoordinator


class FotofeldEntity(CoordinatorEntity[FotofeldCoordinator]):
    """A Fotofeld entity."""

    _attr_has_entity_name = True

    def __init__(self, entry: FotofeldConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.coordinator)
        info = entry.runtime_data.info
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=f"Fotofeld {info.get('server', '')}".strip(),
            manufacturer="Sanfeld",
            model="Fotofeld photo library",
            sw_version=str(info.get("version", "")),
            configuration_url=None,
        )
