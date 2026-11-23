"""Config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from custom_components.fotofeld.const import CONF_CODE, DOMAIN

from .conftest import BASE, INFO

USER = {CONF_HOST: "192.168.1.231", CONF_PORT: 8765, CONF_CODE: "abcd-efgh-jklm"}


async def test_user_flow(hass, fotofeld):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fotofeld SERVER"
    assert result["result"].unique_id == "server"
    # The code is sent upper-case, as the window shows it.
    assert fotofeld.mock_calls[-1][3]["Authorization"] == "Bearer ABCD-EFGH-JKLM"


async def test_wrong_code(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/info", status=401, json={"error": "Wrong pairing code."})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/info", exc=TimeoutError())
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_old_fotofeld(hass, aioclient_mock):
    aioclient_mock.get(f"{BASE}/api/info", json={**INFO, "api": 1})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["errors"] == {"base": "old_version"}


async def test_already_configured(hass, fotofeld, entry):
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options(hass, fotofeld, entry):
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"photo_minutes": 15, "photo_size": 1920, "overdue_days": 7}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["overdue_days"] == 7
