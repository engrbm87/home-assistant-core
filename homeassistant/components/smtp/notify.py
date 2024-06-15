"""Mail (SMTP) notification service."""

from __future__ import annotations

from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import email.utils
import logging
import os
from pathlib import Path
import smtplib
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
    migrate_notify_issue,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    create_issue,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import get_smtp_client
from .const import (
    ATTR_HTML,
    ATTR_IMAGES,
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN as SMTP_DOMAIN,
    ENCRYPTION_OPTIONS,
)

PLATFORMS = [Platform.NOTIFY]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RECIPIENT): vol.All(cv.ensure_list, [vol.Email()]),
        vol.Required(CONF_SENDER): vol.Email(),
        vol.Optional(CONF_SERVER, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): vol.In(
            ENCRYPTION_OPTIONS
        ),
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SENDER_NAME): cv.string,
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

RECIPIENTS_SCHEMA = vol.Schema(vol.All(cv.ensure_list_csv, [vol.Email()]))


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MailNotificationService | None:
    """Get the mail notification service."""
    if discovery_info is None:
        async_create_issue(
            hass,
            SMTP_DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version="2024.9.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                SMTP_DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
        )
        return None

    entry = hass.config_entries.async_get_entry(discovery_info["entry_id"])
    assert isinstance(entry, ConfigEntry)
    config = {**entry.data, **entry.options}
    return MailNotificationService(config)


class MailNotificationService(BaseNotificationService):
    """Implement the notification service for E-mail messages."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the SMTP service."""
        self.config = config

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Build and send a message to a user.

        Will send plain text normally, with pictures as attachments if images config is
        defined, or will build a multipart HTML if html config is defined.
        """
        migrate_notify_issue(
            self.hass,
            SMTP_DOMAIN,
            "SMTP",
            "2024.12.0",
            service_name=self._service_name,
        )
        if not kwargs.get(ATTR_TARGET):
            create_issue(
                self.hass,
                SMTP_DOMAIN,
                "missing_target",
                breaks_in_ha_version="2024.9.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="missing_target",
            )
            if not self.config.get(CONF_RECIPIENT):
                raise ValueError("At least one target recipient is required")

        try:
            recipients = RECIPIENTS_SCHEMA(
                kwargs.get(ATTR_TARGET) or self.config[CONF_RECIPIENT]
            )
        except vol.Invalid as err:
            raise ValueError("Target is not a valid list of email addresses") from err

        subject = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if data := kwargs.get(ATTR_DATA):
            if ATTR_HTML in data:
                msg = _build_html_msg(
                    self.hass,
                    message,
                    data[ATTR_HTML],
                    images=data.get(ATTR_IMAGES, []),
                )
            else:
                msg = _build_multipart_msg(
                    self.hass, message, images=data.get(ATTR_IMAGES, [])
                )
        else:
            msg = _build_text_msg(message)

        msg["Subject"] = subject

        msg["To"] = recipients if isinstance(recipients, str) else ",".join(recipients)

        if sender_name := self.config.get(CONF_SENDER_NAME):
            msg["From"] = f"{sender_name} <{self.config[CONF_SENDER]}>"
        else:
            msg["From"] = self.config[CONF_SENDER]

        msg["X-Mailer"] = "Home Assistant"
        msg["Date"] = email.utils.format_datetime(dt_util.now())
        msg["Message-Id"] = email.utils.make_msgid()

        mail = get_smtp_client(self.config)
        for attempt in range(2):
            try:
                mail.sendmail(self.config[CONF_USERNAME], recipients, msg.as_string())
                break
            except smtplib.SMTPException as err:
                if attempt == 1:
                    mail.quit()
                    raise HomeAssistantError(f"Failed to send message: {err}") from err
                _LOGGER.error("Error sending mail: %s. Retrying connection", err)
                mail.quit()
                mail = get_smtp_client(self.config)
        mail.quit()


def _build_text_msg(message):
    """Build plaintext email."""
    _LOGGER.debug("Building plain text email")
    return MIMEText(message)


def _attach_file(
    hass: HomeAssistant, attach_name: str, content_id: str = ""
) -> MIMEImage | MIMEApplication | None:
    """Create a message attachment.

    If MIMEImage is successful and content_id is passed (HTML), add images in-line.
    Otherwise add them as attachments.
    """
    try:
        file_path = Path(attach_name).parent
        if os.path.exists(file_path) and not hass.config.is_allowed_path(
            str(file_path)
        ):
            allow_list = "allowlist_external_dirs"
            file_name = os.path.basename(attach_name)
            url = "https://www.home-assistant.io/docs/configuration/basic/"
            raise ServiceValidationError(
                translation_domain=SMTP_DOMAIN,
                translation_key="remote_path_not_allowed",
                translation_placeholders={
                    "allow_list": allow_list,
                    "file_path": str(file_path),
                    "file_name": file_name,
                    "url": url,
                },
            )
        with open(attach_name, "rb") as attachment_file:
            file_bytes = attachment_file.read()
    except FileNotFoundError:
        _LOGGER.warning("Attachment %s not found. Skipping", attach_name)
        return None

    try:
        attachment: MIMEApplication | MIMEImage = MIMEImage(file_bytes)
    except TypeError:
        _LOGGER.warning(
            "Attachment %s has an unknown MIME type. Falling back to file",
            attach_name,
        )
        attachment = MIMEApplication(file_bytes, Name=os.path.basename(attach_name))
        attachment["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(attach_name)}"'
        )
    else:
        if content_id:
            attachment.add_header("Content-ID", f"<{content_id}>")
        else:
            attachment.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(attach_name)}",
            )

    return attachment


def _build_multipart_msg(
    hass: HomeAssistant, message: str, images: list[str]
) -> MIMEMultipart:
    """Build Multipart message with images as attachments."""
    _LOGGER.debug("Building multipart email with image attachme_build_html_msgnt(s)")
    msg = MIMEMultipart()
    body_txt = MIMEText(message)
    msg.attach(body_txt)

    for attach_name in images:
        attachment = _attach_file(hass, attach_name)
        if attachment:
            msg.attach(attachment)

    return msg


def _build_html_msg(
    hass: HomeAssistant, text: str, html: str, images: list[str]
) -> MIMEMultipart:
    """Build Multipart message with in-line images and rich HTML (UTF-8)."""
    _LOGGER.debug("Building HTML rich email")
    msg = MIMEMultipart("related")
    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(text, _charset="utf-8"))
    alternative.attach(MIMEText(html, ATTR_HTML, _charset="utf-8"))
    msg.attach(alternative)

    for atch_name in images:
        name = os.path.basename(atch_name)
        attachment = _attach_file(hass, atch_name, name)
        if attachment:
            msg.attach(attachment)
    return msg
