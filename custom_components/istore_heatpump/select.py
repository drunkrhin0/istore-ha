import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, COMMAND_REFRESH_DELAY
from .sensor import _get_point_value

_LOGGER = logging.getLogger(__name__)

WORK_MODES = {
    "Standby": 0,
    "Heating": 1,
    "Eco": 2,
    "Hybrid": 3,
    "Boost": 4,
}
WORK_MODE_REVERSE = {v: k for k, v in WORK_MODES.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities = [IStoreWorkModeSelect(coordinator, api)]
    async_add_entities(entities)


class IStoreWorkModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for changing the heat pump work mode.

    Changing the work mode sends a batch write to the iStore API
    that includes all timer settings alongside the mode value.
    This is required by the API — individual point writes are rejected.
    See ADR-001 D-4 for rationale.
    """

    _attr_name = "iStore Work Mode"
    _attr_icon = "mdi:thermostat"
    _attr_options = list(WORK_MODES.keys())

    def __init__(self, coordinator, api):
        super().__init__(coordinator)
        self.api = api
        self._attr_unique_id = f"istore_{api.mdm_id}_work_mode_select"
        self._attr_device_info = api.device_info

    @property
    def current_option(self):
        value = _get_point_value(self.coordinator, self.api.mdm_id, "PUB_WH.WorkMode")
        if value is None:
            return None
        return WORK_MODE_REVERSE.get(value)

    async def async_select_option(self, option: str):
        value = WORK_MODES.get(option)
        if value is None:
            _LOGGER.error("iStore: rejected invalid work mode: %s", option)
            return
        await self.api.async_write_timer_settings(self.coordinator, {"PUB_WH.WorkMode": value})
        await asyncio.sleep(COMMAND_REFRESH_DELAY)
        await self.coordinator.async_request_refresh()
