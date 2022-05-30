"""Test Mikrotik setup process."""
import librouteros

from homeassistant.components.mikrotik.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from . import MOCK_DATA

from tests.common import MockConfigEntry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, DOMAIN, {}) is True
    assert DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id]


async def test_hub_connection_error(hass, mock_api):
    """Test setup retry due to connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = librouteros.exceptions.ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_hub_auth_error(hass, mock_api):
    """Test setup fails due to auth error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = librouteros.exceptions.TrapError(
        "invalid user name or password"
    )

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
