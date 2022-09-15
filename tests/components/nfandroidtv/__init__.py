"""Tests for the NFAndroidTV integration."""

from homeassistant.const import CONF_HOST, CONF_NAME

HOST = "1.2.3.4"
NAME = "Android TV / Fire TV"

CONF_DATA = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}

CONF_CONFIG_FLOW = {
    CONF_HOST: HOST,
    CONF_NAME: NAME,
}
