"""Notifications for Android TV notification service."""
from __future__ import annotations

import logging
from typing import Any

from notifications_android_tv import (
    BkgColors,
    FontSizes,
    ImageUrlSource,
    Notifications,
    Positions,
    Transparencies,
)
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_BKGCOLOR,
    ATTR_COLOR,
    ATTR_DURATION,
    ATTR_FONTSIZE,
    ATTR_ICON,
    ATTR_ICON_PATH,
    ATTR_ICON_URL,
    ATTR_IMAGE,
    ATTR_IMAGE_PATH,
    ATTR_IMAGE_URL,
    ATTR_INTERRUPT,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> NFAndroidTVNotificationService | None:
    """Get the NFAndroidTV notification service."""
    if discovery_info is None:
        return None
    notify = Notifications(discovery_info[CONF_HOST])
    return NFAndroidTVNotificationService(
        notify,
        hass.config.is_allowed_path,
    )


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(
        self,
        notify: Notifications,
        is_allowed_path: Any,
    ) -> None:
        """Initialize the service."""
        self.notify = notify
        self.is_allowed_path = is_allowed_path

    async def async_send_message(  # noqa: C901
        self, message: str, **kwargs: Any
    ) -> None:
        """Send a message to a Android TV device."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data: dict = kwargs.get(ATTR_DATA) or {}
        if data:
            if ATTR_DURATION in data:
                try:
                    data[ATTR_DURATION] = int(data[ATTR_DURATION])
                except ValueError:
                    _LOGGER.warning("Invalid duration-value: %s", data[ATTR_DURATION])
            if ATTR_FONTSIZE in data:
                try:
                    data[ATTR_FONTSIZE] = FontSizes[data[ATTR_FONTSIZE].upper()]
                except ValueError:
                    _LOGGER.warning("Invalid fontsize-value: %s", data[ATTR_FONTSIZE])
            if ATTR_POSITION in data:
                try:
                    data[ATTR_POSITION] = Positions[
                        data[ATTR_POSITION].upper().replace("-", "_")
                    ]
                except ValueError:
                    _LOGGER.warning("Invalid position-value: %s", data[ATTR_FONTSIZE])
            if ATTR_TRANSPARENCY in data:
                try:
                    data[ATTR_TRANSPARENCY] = Transparencies[
                        f"_{data[ATTR_TRANSPARENCY].replace('%', '_PERCENT')}"
                    ]
                except ValueError:
                    _LOGGER.warning(
                        "Invalid transparency-value: %s",
                        data[ATTR_FONTSIZE],
                    )
            if ATTR_COLOR in data:
                # correct key should be `bkgcolor` so we replace `color` with `bkgcolor`
                try:
                    data[ATTR_BKGCOLOR] = BkgColors[data.pop(ATTR_COLOR).upper()]
                except ValueError:
                    _LOGGER.warning("Invalid color-value: %s", data.get(ATTR_COLOR))
            if ATTR_INTERRUPT in data:
                try:
                    data[ATTR_INTERRUPT] = cv.boolean(data[ATTR_INTERRUPT])
                except vol.Invalid:
                    _LOGGER.warning("Invalid interrupt-value: %s", data[ATTR_INTERRUPT])

            if imagedata := data.pop(ATTR_IMAGE, None):
                if imagedata.get(ATTR_IMAGE_PATH):
                    data["image_file"] = imagedata[ATTR_IMAGE_PATH]
                elif ATTR_IMAGE_URL in imagedata:
                    data["image_file"] = ImageUrlSource(**imagedata)

            if icondata := data.pop(ATTR_ICON, None):
                if icondata.get(ATTR_ICON_PATH):
                    data["icon"] = icondata[ATTR_ICON_PATH]
                elif ATTR_ICON_URL in icondata:
                    data["icon"] = ImageUrlSource(**icondata)

        await self.notify.async_send(message, title=title, **data)
