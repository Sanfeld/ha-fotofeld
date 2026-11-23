"""Setup, entities, events and actions."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_capture_events, async_fire_time_changed

from custom_components.fotofeld.const import DOMAIN, EVENT_BUS

from .conftest import BASE, JPEG, STATS


@pytest.fixture
async def setup(hass: HomeAssistant, fotofeld, entry, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Stockholm")
    freezer.move_to("2026-11-23 12:00:00+01:00")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, setup):
    assert setup.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.fotofeld_server_files_in_library").state == "86331"
    assert hass.states.get("sensor.fotofeld_server_duplicates").state == "63158"
    assert hass.states.get("sensor.fotofeld_server_disk_read_errors").state == "2"
    assert hass.states.get("binary_sensor.fotofeld_server_disk_problem").state == "on"
    assert hass.states.get("binary_sensor.fotofeld_server_busy").state == "off"
    assert hass.states.get("switch.fotofeld_server_paused").state == "off"
    assert hass.states.get("sensor.fotofeld_server_faces_to_name").state == "12"
    # Per-phone entities, and Ma's phone has not backed up for weeks.
    assert hass.states.get("sensor.fotofeld_server_scott_s_phone_last_backup") is not None
    assert hass.states.get("binary_sensor.fotofeld_server_ma_s_phone_backup_overdue").state == "on"
    assert hass.states.get("binary_sensor.fotofeld_server_scott_s_phone_backup_overdue").state == "off"
    assert hass.states.get("binary_sensor.fotofeld_server_phone_backup_overdue").attributes["phones"] == ["Ma's phone"]


async def test_photos(hass: HomeAssistant, setup, hass_client):
    state = hass.states.get("image.fotofeld_server_on_this_day")
    assert state is not None
    assert state.attributes["years_ago"] == 5
    assert hass.states.get("image.fotofeld_server_photo_of_soli") is not None
    client = await hass_client()
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == 200
    assert await resp.read() == JPEG


async def test_next_photo_action(hass: HomeAssistant, setup, fotofeld):
    before = fotofeld.call_count
    await hass.services.async_call(
        DOMAIN, "next_photo", {"mode": "person", "name": "Soli"},
        target={"entity_id": "image.fotofeld_server_photo_frame"}, blocking=True,
    )
    state = hass.states.get("image.fotofeld_server_photo_frame")
    assert state.attributes["mode"] == "person"
    assert state.attributes["filter"] == "Soli"
    assert fotofeld.call_count == before + 2


async def test_find_photo(hass: HomeAssistant, setup):
    result = await hass.services.async_call(DOMAIN, "find_photo", {"mode": "onthisday"}, blocking=True, return_response=True)
    assert result["yearsAgo"] == 5


async def test_pause_and_analyze(hass: HomeAssistant, setup, fotofeld):
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.fotofeld_server_paused"}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": "button.fotofeld_server_analyze_pictures"}, blocking=True)
    paths = [str(c[1]) for c in fotofeld.mock_calls]
    assert f"{BASE}/api/actions/pause" in paths
    assert f"{BASE}/api/actions/vision" in paths


async def test_events(hass: HomeAssistant, setup, fotofeld, freezer):
    bus = async_capture_events(hass, EVENT_BUS)
    fotofeld.clear_requests()
    fotofeld.get(f"{BASE}/api/stats", json={**STATS, "lastEventId": 7})
    fotofeld.get(f"{BASE}/api/events", json={"lastEventId": 7, "events": [
        {"id": 6, "type": "usb_finished", "time": "2026-11-23T12:00:10", "data": {"drive": "F:", "name": "SD", "copied": 31, "result": "done"}},
        {"id": 7, "type": "new_faces", "time": "2026-11-23T12:00:20", "data": {"unnamedFaceGroups": 14}},
    ]})
    fotofeld.get(f"{BASE}/api/people", json={"people": [], "subjects": []})
    fotofeld.get(f"{BASE}/api/photo", json={"id": "abc"})
    fotofeld.get(f"{BASE}/api/photo/file", content=JPEG)
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [e.data["type"] for e in bus] == ["usb_finished", "new_faces"]
    assert bus[0].data["copied"] == 31
    state = hass.states.get("event.fotofeld_server_fotofeld")
    assert state.attributes["event_type"] == "new_faces"


async def test_wrong_code_starts_reauth(hass: HomeAssistant, aioclient_mock, entry):
    aioclient_mock.get(f"{BASE}/api/info", status=401, json={"error": "Wrong pairing code."})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_unload(hass: HomeAssistant, setup):
    assert await hass.config_entries.async_unload(setup.entry_id)
    assert setup.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics(hass: HomeAssistant, setup):
    from custom_components.fotofeld.diagnostics import async_get_config_entry_diagnostics
    d = await async_get_config_entry_diagnostics(hass, setup)
    assert d["entry"]["code"] == "**REDACTED**"
