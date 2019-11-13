"""Tests for Deluge config flow."""
from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.deluge import config_flow
from homeassistant.components.deluge.const import (
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

NAME = "Deluge"
HOST = "192.168.1.100"
USERNAME = "username"
PASSWORD = "password"
PORT = 5555
SCAN_INTERVAL = 10

MOCK_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_PORT: PORT,
}


@pytest.fixture(name="api")
def mock_deluge_api():
    """Mock an api."""
    with patch("deluge_client.DelugeRPCClient.connect"):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.DelugeFlowHandler()
    flow.hass = hass
    return flow


async def test_flow_works(hass, api):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all required provided
    result = await flow.async_step_user(MOCK_ENTRY)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_PORT] == PORT


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data=MOCK_ENTRY,
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    flow = init_config_flow(hass)
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    result = await options_flow.async_step_init({CONF_SCAN_INTERVAL: 10})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 10


async def test_import(hass, api):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with minimum fields only
    result = await flow.async_step_import(
        {
            CONF_NAME: DEFAULT_NAME,
            CONF_HOST: HOST,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "password",
            CONF_PORT: DEFAULT_PORT,
            CONF_SCAN_INTERVAL: timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert result["data"][CONF_USERNAME] == "user"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL

    # import with all
    result = await flow.async_step_import(
        {
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_PORT: PORT,
            CONF_SCAN_INTERVAL: timedelta(seconds=SCAN_INTERVAL),
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_SCAN_INTERVAL] == SCAN_INTERVAL


async def test_host_already_configured(hass, api):
    """Test host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY,
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    entry.add_to_hass(hass)
    flow = init_config_flow(hass)
    result = await flow.async_step_user(MOCK_ENTRY)

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_name_already_configured(hass, api):
    """Test name is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY,
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    entry.add_to_hass(hass)

    mock_entry = MOCK_ENTRY.copy()
    mock_entry[CONF_HOST] = "0.0.0.0"
    flow = init_config_flow(hass)
    result = await flow.async_step_user(mock_entry)

    assert result["type"] == "form"
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_error_on_wrong_credentials(hass):
    """Test with wrong credentials."""
    flow = init_config_flow(hass)

    # test wrong username
    with patch(
        "deluge_client.DelugeRPCClient.connect",
        side_effect=Exception("Username does not exist"),
    ):
        result = await flow.async_step_user(
            {
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_PORT: PORT,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {
            CONF_USERNAME: "user_error",
        }

    # test wrong password
    with patch(
        "deluge_client.DelugeRPCClient.connect",
        side_effect=Exception("Password does not match"),
    ):
        result = await flow.async_step_user(
            {
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_PORT: PORT,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {
            CONF_PASSWORD: "password_error",
        }


async def test_error_on_connection_failure(hass):
    """Test when connection to host fails."""
    flow = init_config_flow(hass)

    with patch(
        "deluge_client.DelugeRPCClient.connect", side_effect=ConnectionRefusedError,
    ):
        result = await flow.async_step_user(
            {
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_PORT: PORT,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_error_on_unknwon_error(hass):
    """Test when connection to host fails."""
    flow = init_config_flow(hass)

    with patch(
        "deluge_client.DelugeRPCClient.connect", side_effect=Exception("timed out"),
    ):
        result = await flow.async_step_user(
            {
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_PORT: PORT,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}
