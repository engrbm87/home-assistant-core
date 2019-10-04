"""Support gathering system information of hosts which are running glances."""
import logging

from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_UPDATED, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Glances sensors is done through async_setup_entry."""
    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Glances sensors."""

    glances_api = hass.data[DOMAIN][config_entry.entry_id]
    client_name = config_entry.data[CONF_NAME]
    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(
            GlancesSensor(
                glances_api, client_name, SENSOR_TYPES[sensor_type][0], sensor_type
            )
        )

    async_add_entities(dev, True)


class GlancesSensor(Entity):
    """Implementation of a Glances sensor."""

    def __init__(self, glances_api, client_name, sensor_name, sensor_type):
        """Initialize the sensor."""
        self.glances_api = glances_api
        self._name = sensor_name
        self.client_name = client_name
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return f"{self.glances_api.host}-{self.name}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.glances_api.available

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Get the latest data from REST API."""
        value = self.glances_api.api.data

        if value is not None:
            if self.type == "disk_use_percent":
                self._state = value["fs"][0]["percent"]
            elif self.type == "disk_use":
                self._state = round(value["fs"][0]["used"] / 1024 ** 3, 1)
            elif self.type == "disk_free":
                try:
                    self._state = round(value["fs"][0]["free"] / 1024 ** 3, 1)
                except KeyError:
                    self._state = round(
                        (value["fs"][0]["size"] - value["fs"][0]["used"]) / 1024 ** 3, 1
                    )
            elif self.type == "memory_use_percent":
                self._state = value["mem"]["percent"]
            elif self.type == "memory_use":
                self._state = round(value["mem"]["used"] / 1024 ** 2, 1)
            elif self.type == "memory_free":
                self._state = round(value["mem"]["free"] / 1024 ** 2, 1)
            elif self.type == "swap_use_percent":
                self._state = value["memswap"]["percent"]
            elif self.type == "swap_use":
                self._state = round(value["memswap"]["used"] / 1024 ** 3, 1)
            elif self.type == "swap_free":
                self._state = round(value["memswap"]["free"] / 1024 ** 3, 1)
            elif self.type == "processor_load":
                # Windows systems don't provide load details
                try:
                    self._state = value["load"]["min15"]
                except KeyError:
                    self._state = value["cpu"]["total"]
            elif self.type == "process_running":
                self._state = value["processcount"]["running"]
            elif self.type == "process_total":
                self._state = value["processcount"]["total"]
            elif self.type == "process_thread":
                self._state = value["processcount"]["thread"]
            elif self.type == "process_sleeping":
                self._state = value["processcount"]["sleeping"]
            elif self.type == "cpu_use_percent":
                self._state = value["quicklook"]["cpu"]
            elif self.type == "cpu_temp":
                for sensor in value["sensors"]:
                    if sensor["label"] in [
                        "amdgpu 1",
                        "aml_thermal",
                        "Core 0",
                        "Core 1",
                        "CPU Temperature",
                        "CPU",
                        "cpu-thermal 1",
                        "cpu_thermal 1",
                        "exynos-therm 1",
                        "Package id 0",
                        "Physical id 0",
                        "radeon 1",
                        "soc-thermal 1",
                        "soc_thermal 1",
                    ]:
                        self._state = sensor["value"]
            elif self.type == "docker_active":
                count = 0
                try:
                    for container in value["docker"]["containers"]:
                        if (
                            container["Status"] == "running"
                            or "Up" in container["Status"]
                        ):
                            count += 1
                    self._state = count
                except KeyError:
                    self._state = count
            elif self.type == "docker_cpu_use":
                cpu_use = 0.0
                try:
                    for container in value["docker"]["containers"]:
                        if (
                            container["Status"] == "running"
                            or "Up" in container["Status"]
                        ):
                            cpu_use += container["cpu"]["total"]
                        self._state = round(cpu_use, 1)
                except KeyError:
                    self._state = STATE_UNAVAILABLE
            elif self.type == "docker_memory_use":
                mem_use = 0.0
                try:
                    for container in value["docker"]["containers"]:
                        if (
                            container["Status"] == "running"
                            or "Up" in container["Status"]
                        ):
                            mem_use += container["memory"]["usage"]
                        self._state = round(mem_use / 1024 ** 2, 1)
                except KeyError:
                    self._state = STATE_UNAVAILABLE
