"""Test different accessory types: Fans."""
from collections import namedtuple
from unittest.mock import Mock

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_SPEED,
    ATTR_SPEED_LIST,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_OFF,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
)
from homeassistant.components.homekit.const import ATTR_VALUE
from homeassistant.components.homekit.util import HomeKitSpeedMapping
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState
from homeassistant.helpers import entity_registry

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope="module")
def cls():
    """Patch debounce decorator during import of type_fans."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__("homeassistant.components.homekit.type_fans", fromlist=["Fan"])
    patcher_tuple = namedtuple("Cls", ["fan"])
    yield patcher_tuple(fan=_import.Fan)
    patcher.stop()


async def test_fan_basic(hass, hk_driver, cls, events):
    """Test fan with char state."""
    entity_id = "fan.demo"

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.aid == 1
    assert acc.category == 3  # Fan
    assert acc.char_active.value == 1

    # If there are no speed_list values, then HomeKit speed is unsupported
    assert acc.char_speed is None

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_active.value == 1

    hass.states.async_set(entity_id, STATE_OFF, {ATTR_SUPPORTED_FEATURES: 0})
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_on
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


async def test_fan_direction(hass, hk_driver, cls, events):
    """Test fan with direction."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_DIRECTION, ATTR_DIRECTION: DIRECTION_FORWARD},
    )
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_direction.value == 0

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_direction.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_DIRECTION: DIRECTION_REVERSE})
    await hass.async_block_till_done()
    assert acc.char_direction.value == 1

    # Set from HomeKit
    call_set_direction = async_mock_service(hass, DOMAIN, "set_direction")

    char_direction_iid = acc.char_direction.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_FORWARD
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == DIRECTION_FORWARD

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_add_executor_job(acc.char_direction.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == DIRECTION_REVERSE


async def test_fan_oscillate(hass, hk_driver, cls, events):
    """Test fan with oscillate."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_SUPPORTED_FEATURES: SUPPORT_OSCILLATE, ATTR_OSCILLATING: False},
    )
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_swing.value == 0

    await acc.run_handler()
    await hass.async_block_till_done()
    assert acc.char_swing.value == 0

    hass.states.async_set(entity_id, STATE_ON, {ATTR_OSCILLATING: True})
    await hass.async_block_till_done()
    assert acc.char_swing.value == 1

    # Set from HomeKit
    call_oscillate = async_mock_service(hass, DOMAIN, "oscillate")

    char_swing_iid = acc.char_swing.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_add_executor_job(acc.char_swing.client_update_value, 0)
    await hass.async_block_till_done()
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is False
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is False

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_add_executor_job(acc.char_swing.client_update_value, 1)
    await hass.async_block_till_done()
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is True


async def test_fan_speed(hass, hk_driver, cls, events):
    """Test fan with speed."""
    entity_id = "fan.demo"
    speed_list = [SPEED_OFF, SPEED_LOW, SPEED_HIGH]

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED,
            ATTR_SPEED: SPEED_OFF,
            ATTR_SPEED_LIST: speed_list,
        },
    )
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # speed to 100 when turning on a fan on a freshly booted up server.
    assert acc.char_speed.value != 0

    await acc.run_handler()
    await hass.async_block_till_done()

    assert (
        acc.speed_mapping.speed_ranges == HomeKitSpeedMapping(speed_list).speed_ranges
    )

    acc.speed_mapping.speed_to_homekit = Mock(return_value=42)
    acc.speed_mapping.speed_to_states = Mock(return_value="ludicrous")

    hass.states.async_set(entity_id, STATE_ON, {ATTR_SPEED: SPEED_HIGH})
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_homekit.assert_called_with(SPEED_HIGH)
    assert acc.char_speed.value == 42

    # Set from HomeKit
    call_set_speed = async_mock_service(hass, DOMAIN, "set_speed")

    char_speed_iid = acc.char_speed.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_add_executor_job(acc.char_speed.client_update_value, 42)
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_states.assert_called_with(42)
    assert call_set_speed[0]
    assert call_set_speed[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_speed[0].data[ATTR_SPEED] == "ludicrous"
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "ludicrous"


async def test_fan_set_all_one_shot(hass, hk_driver, cls, events):
    """Test fan with speed."""
    entity_id = "fan.demo"
    speed_list = [SPEED_OFF, SPEED_LOW, SPEED_HIGH]

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED
            | SUPPORT_OSCILLATE
            | SUPPORT_DIRECTION,
            ATTR_SPEED: SPEED_OFF,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
            ATTR_SPEED_LIST: speed_list,
        },
    )
    await hass.async_block_till_done()
    acc = cls.fan(hass, hk_driver, "Fan", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    # Initial value can be anything but 0. If it is 0, it might cause HomeKit to set the
    # speed to 100 when turning on a fan on a freshly booted up server.
    assert acc.char_speed.value != 0
    await acc.run_handler()
    await hass.async_block_till_done()

    assert (
        acc.speed_mapping.speed_ranges == HomeKitSpeedMapping(speed_list).speed_ranges
    )

    acc.speed_mapping.speed_to_homekit = Mock(return_value=42)
    acc.speed_mapping.speed_to_states = Mock(return_value="ludicrous")

    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED
            | SUPPORT_OSCILLATE
            | SUPPORT_DIRECTION,
            ATTR_SPEED: SPEED_OFF,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
            ATTR_SPEED_LIST: speed_list,
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    # Set from HomeKit
    call_set_speed = async_mock_service(hass, DOMAIN, "set_speed")
    call_oscillate = async_mock_service(hass, DOMAIN, "oscillate")
    call_set_direction = async_mock_service(hass, DOMAIN, "set_direction")
    call_turn_on = async_mock_service(hass, DOMAIN, "turn_on")
    call_turn_off = async_mock_service(hass, DOMAIN, "turn_off")

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]
    char_direction_iid = acc.char_direction.to_HAP()[HAP_REPR_IID]
    char_swing_iid = acc.char_swing.to_HAP()[HAP_REPR_IID]
    char_speed_iid = acc.char_speed.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_states.assert_called_with(42)
    assert not call_turn_on
    assert call_set_speed[0]
    assert call_set_speed[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_speed[0].data[ATTR_SPEED] == "ludicrous"
    assert call_oscillate[0]
    assert call_oscillate[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[0].data[ATTR_OSCILLATING] is True
    assert call_set_direction[0]
    assert call_set_direction[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[0].data[ATTR_DIRECTION] == DIRECTION_REVERSE
    assert len(events) == 3

    assert events[0].data[ATTR_VALUE] is True
    assert events[1].data[ATTR_VALUE] == DIRECTION_REVERSE
    assert events[2].data[ATTR_VALUE] == "ludicrous"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: SUPPORT_SET_SPEED
            | SUPPORT_OSCILLATE
            | SUPPORT_DIRECTION,
            ATTR_SPEED: SPEED_OFF,
            ATTR_OSCILLATING: False,
            ATTR_DIRECTION: DIRECTION_FORWARD,
            ATTR_SPEED_LIST: speed_list,
        },
    )
    await hass.async_block_till_done()

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    # Turn on should not be called if its already on
    # and we set a fan speed
    await hass.async_block_till_done()
    acc.speed_mapping.speed_to_states.assert_called_with(42)
    assert len(events) == 6
    assert call_set_speed[1]
    assert call_set_speed[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_speed[1].data[ATTR_SPEED] == "ludicrous"
    assert call_oscillate[1]
    assert call_oscillate[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_oscillate[1].data[ATTR_OSCILLATING] is True
    assert call_set_direction[1]
    assert call_set_direction[1].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_direction[1].data[ATTR_DIRECTION] == DIRECTION_REVERSE

    assert events[-3].data[ATTR_VALUE] is True
    assert events[-2].data[ATTR_VALUE] == DIRECTION_REVERSE
    assert events[-1].data[ATTR_VALUE] == "ludicrous"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_speed_iid,
                    HAP_REPR_VALUE: 42,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_swing_iid,
                    HAP_REPR_VALUE: 1,
                },
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_direction_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()

    assert len(events) == 7
    assert call_turn_off
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert len(call_set_speed) == 2
    assert len(call_oscillate) == 2
    assert len(call_set_direction) == 2


async def test_fan_restore(hass, hk_driver, cls, events):
    """Test setting up an entity from state in the event registry."""
    hass.state = CoreState.not_running

    registry = await entity_registry.async_get_registry(hass)

    registry.async_get_or_create(
        "fan", "generic", "1234", suggested_object_id="simple",
    )
    registry.async_get_or_create(
        "fan",
        "generic",
        "9012",
        suggested_object_id="all_info_set",
        capabilities={"speed_list": ["off", "low", "medium", "high"]},
        supported_features=SUPPORT_SET_SPEED | SUPPORT_OSCILLATE | SUPPORT_DIRECTION,
        device_class="mock-device-class",
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START, {})
    await hass.async_block_till_done()

    acc = cls.fan(hass, hk_driver, "Fan", "fan.simple", 2, None)
    assert acc.category == 3
    assert acc.char_active is not None
    assert acc.char_direction is None
    assert acc.char_speed is None
    assert acc.char_swing is None

    acc = cls.fan(hass, hk_driver, "Fan", "fan.all_info_set", 2, None)
    assert acc.category == 3
    assert acc.char_active is not None
    assert acc.char_direction is not None
    assert acc.char_speed is not None
    assert acc.char_swing is not None
