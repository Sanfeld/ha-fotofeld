"""Fotofeld sensors: library counts, phones, USB imports, sorts, the disk and Vision."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfInformation, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .coordinator import FotofeldConfigEntry, parse_time
from .entity import FotofeldEntity


def _get(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _run_total(run: dict | None, *actions: str) -> int | None:
    if not run:
        return None
    counts = run.get("counts") or {}
    return sum(int(counts.get(a, 0)) for a in actions)


@dataclass(frozen=True, kw_only=True)
class FotofeldSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]
    attrs_fn: Callable[[dict], dict] | None = None


SENSORS: tuple[FotofeldSensorDescription, ...] = (
    FotofeldSensorDescription(
        key="library_files", translation_key="library_files", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("libraryFiles"),
    ),
    FotofeldSensorDescription(
        key="sorted_files", translation_key="sorted_files", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("sortedFiles"),
    ),
    FotofeldSensorDescription(
        key="not_sure_files", translation_key="not_sure_files", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("notSureFiles"),
    ),
    FotofeldSensorDescription(
        key="duplicate_files", translation_key="duplicate_files", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.get("duplicateFiles"),
    ),
    FotofeldSensorDescription(
        key="last_filed", translation_key="last_filed", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: parse_time(s.get("lastFiled")),
    ),
    FotofeldSensorDescription(
        key="activity", translation_key="activity",
        value_fn=lambda s: "paused" if s.get("paused") else (s.get("activity") or ("busy" if s.get("busy") else "idle"))[:250],
    ),
    FotofeldSensorDescription(
        key="usb_import", translation_key="usb_import", device_class=SensorDeviceClass.ENUM, options=["idle", "importing"],
        value_fn=lambda s: _get(s, "usb", "state") or "idle",
        attrs_fn=lambda s: {k: v for k, v in (s.get("usb") or {}).items() if k != "state"},
    ),
    FotofeldSensorDescription(
        key="last_usb_import", translation_key="last_usb_import", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: parse_time(_get(s, "runs", "usb", "finished")),
        attrs_fn=lambda s: {
            "copied": _run_total(_get(s, "runs", "usb"), "Copy", "Extract"),
            "errors": _get(s, "runs", "usb", "errors"),
            "log": _get(s, "runs", "usb", "log"),
        },
    ),
    FotofeldSensorDescription(
        key="last_sort", translation_key="last_sort", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: parse_time(_get(s, "runs", "sort", "finished")),
        attrs_fn=lambda s: {
            "dry_run": _get(s, "runs", "sort", "dryRun"),
            "counts": _get(s, "runs", "sort", "counts"),
            "errors": _get(s, "runs", "sort", "errors"),
            "log": _get(s, "runs", "sort", "log"),
        },
    ),
    FotofeldSensorDescription(
        key="disk_free", translation_key="disk_free", device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES, suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=0, state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _get(s, "disk", "freeBytes"),
        attrs_fn=lambda s: {"drive": _get(s, "disk", "drive"), "size_bytes": _get(s, "disk", "sizeBytes")},
    ),
    FotofeldSensorDescription(
        key="disk_used", translation_key="disk_used", native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1, state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: (
            round(100 * (1 - s["disk"]["freeBytes"] / s["disk"]["sizeBytes"]), 1)
            if _get(s, "disk", "sizeBytes") and _get(s, "disk", "freeBytes") is not None else None
        ),
    ),
    FotofeldSensorDescription(
        key="disk_health", translation_key="disk_health", entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: _get(s, "disk", "health"),
        attrs_fn=lambda s: {"model": _get(s, "disk", "model"), "drive": _get(s, "disk", "drive"), "wear": _get(s, "disk", "wear")},
    ),
    FotofeldSensorDescription(
        key="disk_read_errors", translation_key="disk_read_errors", entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s: _get(s, "disk", "readErrors"),
    ),
    FotofeldSensorDescription(
        key="disk_temperature", translation_key="disk_temperature", entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _get(s, "disk", "temperature") or None,
    ),
    FotofeldSensorDescription(
        key="vision_progress", translation_key="vision_progress", native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.get("visionProgress") if s.get("visionRunning") else None,
        attrs_fn=lambda s: {
            "step": s.get("visionStep") if s.get("visionRunning") else None,
            "seconds_left": s.get("visionSecondsLeft") if s.get("visionRunning") else None,
            "started": s.get("visionStarted") if s.get("visionRunning") else None,
        },
    ),
    FotofeldSensorDescription(
        key="last_analysis", translation_key="last_analysis", device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s: parse_time(_get(s, "vision", "finished")),
        attrs_fn=lambda s: {
            "pictures": _get(s, "vision", "pictures"),
            "not_photos": _get(s, "vision", "notPhotos"),
            "look_alike_groups": _get(s, "vision", "lookAlikeGroups"),
            "not_analyzed": _get(s, "vision", "notAnalyzed"),
            "subjects": _get(s, "vision", "subjects"),
        },
    ),
    FotofeldSensorDescription(
        key="unnamed_face_groups", translation_key="unnamed_face_groups", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: _get(s, "vision", "unnamedFaceGroups"),
    ),
    FotofeldSensorDescription(
        key="people", translation_key="people", state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(_get(s, "vision", "people") or {}) if s.get("vision") else None,
        attrs_fn=lambda s: {"photos": _get(s, "vision", "people")},
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: FotofeldConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(FotofeldSensor(entry, d) for d in SENSORS)

    # One "last backup" sensor per phone folder; new phones appear as they first back up.
    known: set[str] = set()

    @callback
    def add_phones() -> None:
        new = [p["name"] for p in coordinator.data.get("phones") or [] if p.get("name") and p["name"] not in known]
        if new:
            known.update(new)
            async_add_entities(PhoneBackupSensor(entry, name) for name in new)

    add_phones()
    entry.async_on_unload(coordinator.async_add_listener(add_phones))


class FotofeldSensor(FotofeldEntity, SensorEntity):
    entity_description: FotofeldSensorDescription

    def __init__(self, entry: FotofeldConfigEntry, description: FotofeldSensorDescription) -> None:
        super().__init__(entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)


class PhoneBackupSensor(FotofeldEntity, SensorEntity):
    """When a phone last backed up to its folder."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "phone_backup"

    def __init__(self, entry: FotofeldConfigEntry, phone: str) -> None:
        super().__init__(entry, f"phone_{slugify(phone)}_backup")
        self.phone = phone
        self._attr_translation_placeholders = {"phone": phone}

    def _phone(self) -> dict:
        return next((p for p in self.coordinator.data.get("phones") or [] if p.get("name") == self.phone), {})

    @property
    def native_value(self):
        return parse_time(self._phone().get("lastBackup"))

    @property
    def extra_state_attributes(self) -> dict:
        p = self._phone()
        return {"folder": self.phone, "files": p.get("files"), "overdue": self.coordinator.phone_overdue(p) if p else None}
