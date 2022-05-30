"""Errors for the Mikrotik component."""
from homeassistant.exceptions import HomeAssistantError


class MikrotikBaseError(HomeAssistantError):
    """Mikrotik base error."""


class CannotConnect(MikrotikBaseError):
    """Unable to connect to the hub."""


class LoginError(MikrotikBaseError):
    """Component got logged out."""
