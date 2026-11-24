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


async def test_frame_select(hass: HomeAssistant, setup, fotofeld):
    sel = "select.fotofeld_server_photo_frame_shows"
    assert hass.states.get(sel).state == "random"
    assert "Person: Soli" in hass.states.get(sel).attributes["options"]
    await hass.services.async_call("select", "select_option", {"entity_id": sel, "option": "Person: Soli"}, blocking=True)
    await hass.async_block_till_done()
    frame = hass.states.get("image.fotofeld_server_photo_frame")
    assert frame.attributes["mode"] == "person"
    assert frame.attributes["filter"] == "Soli"
    assert hass.states.get(sel).state == "Person: Soli"
    # next_photo on the frame updates the select too
    await hass.services.async_call(DOMAIN, "next_photo", {"mode": "onthisday"},
                                   target={"entity_id": "image.fotofeld_server_photo_frame"}, blocking=True)
    assert hass.states.get(sel).state == "onthisday"


async def test_duplicates_viewer(hass: HomeAssistant, setup, fotofeld):
    await hass.async_block_till_done()
    o = hass.states.get("image.fotofeld_server_duplicate_check_original")
    d = hass.states.get("image.fotofeld_server_duplicate_check_duplicate")
    assert o.attributes["original_path"] == "Sorted\\2014\\04\\a.jpg"
    assert d.attributes["duplicate_number"] == 1
    assert d.attributes["duplicates_of_this_original"] == 2
    assert d.attributes["same_size"] is True
    assert d.attributes["kind"] == "copy in _Duplicates"
    await hass.services.async_call("button", "press", {"entity_id": "button.fotofeld_server_next_duplicate"}, blocking=True)
    d = hass.states.get("image.fotofeld_server_duplicate_check_duplicate")
    assert d.attributes["duplicate_number"] == 2
    assert d.attributes["kind"] == "left in place (only listed)"
    await hass.services.async_call("button", "press", {"entity_id": "button.fotofeld_server_next_original"}, blocking=True)
    assert hass.states.get("image.fotofeld_server_duplicate_check_duplicate").attributes["duplicate_number"] == 1
    assert hass.states.get("image.fotofeld_server_duplicate_check_original").attributes["original_number"] == 2
    await hass.services.async_call("text", "set_value", {"entity_id": "text.fotofeld_server_duplicate_check_filter", "value": "2014"}, blocking=True)
    assert hass.states.get("text.fotofeld_server_duplicate_check_filter").state == "2014"
    assert hass.states.get("image.fotofeld_server_duplicate_check_original").attributes["filter"] == "2014"
    assert any("q=2014" in str(c[1]) for c in fotofeld.mock_calls)


async def test_duplicates_viewer_old_server(hass: HomeAssistant, aioclient_mock, fotofeld, entry, freezer):
    # Fotofeld 1.1 has no /api/dups: the viewer entities are unavailable, the rest works.
    fotofeld.clear_requests()
    from .conftest import INFO, STATS, PEOPLE, PHOTO, JPEG, BASE as B
    aioclient_mock.get(f"{B}/api/info", json=INFO)
    aioclient_mock.get(f"{B}/api/stats", json=STATS)
    aioclient_mock.get(f"{B}/api/people", json=PEOPLE)
    aioclient_mock.get(f"{B}/api/photo", json=PHOTO)
    aioclient_mock.get(f"{B}/api/photo/file", content=JPEG)
    aioclient_mock.get(f"{B}/api/dups", status=404, json={"error": "Unknown request."})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("image.fotofeld_server_duplicate_check_original").state == "unavailable"
    assert hass.states.get("sensor.fotofeld_server_files_in_library").state == "86331"


async def test_delete_duplicate(hass: HomeAssistant, setup, fotofeld):
    await hass.async_block_till_done()
    await hass.services.async_call("button", "press", {"entity_id": "button.fotofeld_server_delete_this_duplicate"}, blocking=True)
    sent = [c for c in fotofeld.mock_calls if str(c[1]).endswith("/api/dups/delete")]
    assert len(sent) == 1
    assert sent[0][2] == {"paths": ["E:\\Fotofeld\\Sorted\\_Duplicates\\2014\\04\\a.jpg"], "permanent": False}
    d = hass.states.get("image.fotofeld_server_duplicate_check_duplicate")
    assert d.attributes["last_delete"] == "1 deleted, 1 kept: The original is gone."
    await hass.services.async_call("button", "press", {"entity_id": "button.fotofeld_server_delete_all_duplicates_of_this_original"}, blocking=True)
    sent = [c for c in fotofeld.mock_calls if str(c[1]).endswith("/api/dups/delete")]
    assert len(sent[-1][2]["paths"]) == 2


async def test_duplicates_viewer_waits_while_fotofeld_reads(hass: HomeAssistant, aioclient_mock, entry, freezer):
    from .conftest import INFO, STATS, PEOPLE, PHOTO, JPEG, DUPS, BASE as B
    for path, kw in [("/api/info", {"json": INFO}), ("/api/stats", {"json": STATS}), ("/api/people", {"json": PEOPLE}),
                     ("/api/photo", {"json": PHOTO}), ("/api/photo/file", {"content": JPEG}), ("/api/dups/image", {"content": JPEG})]:
        aioclient_mock.get(f"{B}{path}", **kw)
    aioclient_mock.get(f"{B}/api/dups", status=503, json={"building": True, "error": "Fotofeld is reading the sort logs (20 s so far)."})
    await hass.config.async_set_time_zone("Europe/Stockholm")
    freezer.move_to("2026-11-24 05:00:00+01:00")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    o = hass.states.get("image.fotofeld_server_duplicate_check_original")
    assert o.attributes["error"] == "Fotofeld is reading the sort logs (20 s so far)."
    # Fotofeld has finished reading: the next try (15 s later) shows the duplicates.
    aioclient_mock.clear_requests()
    for path, kw in [("/api/info", {"json": INFO}), ("/api/stats", {"json": STATS}), ("/api/events", {"json": {"lastEventId": 5, "events": []}}),
                     ("/api/dups", {"json": DUPS}), ("/api/dups/image", {"content": JPEG})]:
        aioclient_mock.get(f"{B}{path}", **kw)
    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    o = hass.states.get("image.fotofeld_server_duplicate_check_original")
    assert "error" not in o.attributes
    assert o.attributes["original_number"] == 1
