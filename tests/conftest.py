"""Fixtures: a fake Fotofeld service."""

from __future__ import annotations

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fotofeld.const import CONF_CODE, DOMAIN

BASE = "http://192.168.1.231:8765"
INFO = {"name": "Fotofeld", "api": 2, "version": "1.1.0", "server": "SERVER", "features": ["stats", "events", "photos"]}
STATS = {
    "name": "Fotofeld", "version": "1.1.0", "server": "SERVER", "folder": "E:\\Fotofeld", "updated": "2026-11-23T12:00:00",
    "libraryFiles": 86331, "sortedFiles": 23109, "notSureFiles": 120, "duplicateFiles": 63158, "lastFiled": "2026-11-23T11:58:00",
    "phones": [
        {"name": "Scott's phone", "lastBackup": "2026-11-23T11:00:00", "files": 4000},
        {"name": "Ma's phone", "lastBackup": "2026-10-01T10:00:00", "files": 900},
    ],
    "usb": {"state": "idle"},
    "runs": {"sort": {"kind": "sort", "finished": "2026-11-21T23:00:00", "dryRun": False, "counts": {"Copy": 23109}, "errors": 0, "log": "x"}},
    "disk": {"drive": "E:", "model": "WDC WD30EFRX", "health": "Healthy", "readErrors": 2, "temperature": 34, "wear": 0,
             "freeBytes": 1_000_000_000_000, "sizeBytes": 3_000_000_000_000},
    "vision": {"finished": "2026-11-22T20:00:00", "pictures": 23000, "notPhotos": 900, "lookAlikeGroups": 300,
               "unnamedFaceGroups": 12, "notAnalyzed": 0, "unreadable": 1, "people": {"Soli": 400}, "subjects": {"Midsummer": 80}},
    "busy": False, "paused": False, "activity": "", "visionRunning": False, "visionProgress": None, "lastEventId": 5,
}
PEOPLE = {"people": [{"name": "Soli", "photos": 400}], "subjects": [{"name": "Midsummer", "photos": 80}]}
PHOTO = {"id": "abc", "path": "Sorted\\2021\\11\\x.jpg", "date": "2021-11-23", "yearsAgo": 5, "people": ["Soli"], "subjects": [], "matches": 3}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, unique_id="server", title="Fotofeld SERVER",
        data={CONF_HOST: "192.168.1.231", CONF_PORT: 8765, CONF_CODE: "ABCD-EFGH-JKLM"},
    )


@pytest.fixture
def fotofeld(aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/info", json=INFO)
    aioclient_mock.get(f"{BASE}/api/stats", json=STATS)
    aioclient_mock.get(f"{BASE}/api/people", json=PEOPLE)
    aioclient_mock.get(f"{BASE}/api/events", json={"lastEventId": 5, "events": []})
    aioclient_mock.get(f"{BASE}/api/photo", json=PHOTO)
    aioclient_mock.get(f"{BASE}/api/photo/file", content=JPEG, headers={"Content-Type": "image/jpeg"})
    aioclient_mock.post(f"{BASE}/api/actions/vision", json={"result": "started"})
    aioclient_mock.post(f"{BASE}/api/actions/pause", json={"paused": True})
    aioclient_mock.post(f"{BASE}/api/actions/resume", json={"paused": False})
    return aioclient_mock
