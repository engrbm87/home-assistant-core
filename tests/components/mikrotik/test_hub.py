"""Test Mikrotik hub."""
from unittest.mock import patch

from homeassistant.components import mikrotik

from . import ARP_DATA, DHCP_DATA, MOCK_DATA, PING_FAIL, PING_SUCCESS, WIRELESS_DATA

from tests.common import MockConfigEntry


async def setup_mikrotik_entry(
    hass,
    config_entry,
    support_capsman=True,
    support_wireless=True,
    dhcp_data=DHCP_DATA,
    wireless_data=WIRELESS_DATA,
    arp_data=ARP_DATA,
    ping_result=PING_SUCCESS,
    force_dhcp=False,
    arp_ping=False,
) -> mikrotik.MikrotikHub:
    """Set up Mikrotik integration successfully."""

    def mock_command(self, cmd, params=None):
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_CAPSMAN]:
            return support_capsman
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
            return support_wireless
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
            return dhcp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.CAPSMAN]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.ARP]:
            return arp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IDENTITY]:
            return [{"name": "router"}]
        if cmd == "/ping":
            return ping_result
        return {}

    if force_dhcp:
        config_entry.options = {**config_entry.options, "force_dhcp": True}

    if arp_ping:
        config_entry.options = {**config_entry.options, "arp_ping": True}

    with patch.object(mikrotik.hub.MikrotikData, "command", new=mock_command):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return hass.data[mikrotik.DOMAIN][config_entry.entry_id]


async def test_hub_not_support_wireless(hass):
    """Test updating hub devices when hub doesn't support wireless interfaces."""

    # test that the devices are constructed from dhcp data
    entry = MockConfigEntry(domain=mikrotik.const.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(
        hass, entry, support_capsman=False, support_wireless=False
    )

    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params is None
    assert hub.api.devices["00:00:00:00:00:02"]._params == DHCP_DATA[1]
    assert hub.api.devices["00:00:00:00:00:02"]._wireless_params is None


async def test_hub_support_wireless(hass):
    """Test updating hub devices when hub support wireless interfaces."""

    # test that the device list is from wireless data list
    entry = MockConfigEntry(domain=mikrotik.const.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry)

    assert hub.api.support_wireless is True
    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params == WIRELESS_DATA[0]

    # devices not in wireless list will not be added
    assert "00:00:00:00:00:02" not in hub.api.devices


async def test_force_dhcp(hass):
    """Test updating hub devices with forced dhcp method."""

    # test that the devices are constructed from dhcp data
    entry = MockConfigEntry(domain=mikrotik.const.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry, force_dhcp=True)

    assert hub.api.support_wireless is True
    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params == WIRELESS_DATA[0]

    # devices not in wireless list are added from dhcp
    assert hub.api.devices["00:00:00:00:00:02"]._params == DHCP_DATA[1]
    assert hub.api.devices["00:00:00:00:00:02"]._wireless_params is None


async def test_arp_ping(hass):
    """Test arp ping devices to confirm they are connected."""

    entry = MockConfigEntry(domain=mikrotik.const.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(hass, entry, force_dhcp=True, arp_ping=True)

    assert hub.api.devices["00:00:00:00:00:01"].last_seen is not None
    assert hub.api.devices["00:00:00:00:00:02"].last_seen is not None


async def test_arp_ping_timeout(hass):
    """Test arp ping timeout to confirm if client is not connected."""

    entry = MockConfigEntry(domain=mikrotik.const.DOMAIN, data=MOCK_DATA)
    entry.add_to_hass(hass)
    hub = await setup_mikrotik_entry(
        hass, entry, force_dhcp=True, arp_ping=True, ping_result=PING_FAIL
    )

    assert hub.api.devices["00:00:00:00:00:01"].last_seen is not None
    # this device is not wireless so it will show as away
    assert hub.api.devices["00:00:00:00:00:02"].last_seen is None
