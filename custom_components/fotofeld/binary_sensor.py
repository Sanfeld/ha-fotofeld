"""Fotofeld binary sensors: busy, disk problem, Vision running, phones overdue."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .coordinator import FotofeldConfigEntry
from .entity import FotofeldEntity


def _disk_problem(s: dict) -> bool | None:
    disk = s.get("disk") or {}
    if not disk:
        return None
    return (disk.get("health") not in (None, "Healthy", "Unknown")) or bool(disk.get("readErrors"))


@dataclass(frozen=True, kw_only=True)
class FotofeldBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], bool | None]


BINARY_SENSORS = (
    FotofeldBinaryDescription(
        key="busy", translation_key="busy", device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: bool(s.get("busy")),
    ),
    FotofeldBinaryDescription(
        key="disk_problem", translation_key="disk_problem", device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_disk_problem,
    ),
    FotofeldBinaryDescription(
        key="vision_running", translation_key="vision_running", device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=lambda s: bool(s.get("visionRunning")),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([FotofeldBinary(entry, d) for d in BINARY_SENSORS] + [AnyPhoneOverdue(entry)])
    known: set[str] = set()

    @callback
    def add_phones() -> None:
        new = [p["name"] for p in coordinator.data.get("phones") or [] if p.get("name") and p["name"] not in known]
        if new:
            known.update(new)
            async_add_entities(PhoneOverdue(entry, name) for name in new)

    add_phones()
    entry.async_on_unload(coordinator.async_add_listener(add_phones))


class FotofeldBinary(FotofeldEntity, BinarySensorEntity):
    entity_description: FotofeldBinaryDescription

    def __init__(self, entry: FotofeldConfigEntry, description: FotofeldBinaryDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)


class PhoneOverdue(FotofeldEntity, BinarySensorEntity):
    """On when a phone has not backed up for longer than the configured number of days."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "phone_overdue"

    def __init__(self, entry: FotofeldConfigEntry, phone: str) -> None:
        super().__init__(entry, f"phone_{slugify(phone)}_overdue")
        self.phone = phone
        self._attr_translation_placeholders = {"phone": phone}

    @property
    def is_on(self) -> bool:
        p = next((p for p in self.coordinator.data.get("phones") or [] if p.get("name") == self.phone), None)
        return bool(p and self.coordinator.phone_overdue(p))


class AnyPhoneOverdue(FotofeldEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "any_phone_overdue"

    def __init__(self, entry: FotofeldConfigEntry) -> None:
        super().__init__(entry, "any_phone_overdue")

    @property
    def is_on(self) -> bool:
        return any(self.coordinator.phone_overdue(p) for p in self.coordinator.data.get("phones") or [])

    @property
    def extra_state_attributes(self) -> dict:
        return {"phones": [p["name"] for p in self.coordinator.data.get("phones") or [] if self.coordinator.phone_overdue(p)]}
