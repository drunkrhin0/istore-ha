import asyncio
import logging
import re
from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, COMMAND_REFRESH_DELAY
from .sensor import _get_point_value

_LOGGER = logging.getLogger(__name__)

TIME_POINTS = {
    "timer1_on_time": ("PRI_RE_WH.Timer1OnTime", "Timer 1 On"),
    "timer1_off_time": ("PRI_RE_WH.Timer1OffTime", "Timer 1 Off"),
    "timer2_on_time": ("PRI_RE_WH.Timer2OnTime", "Timer 2 On"),
    "timer2_off_time": ("PRI_RE_WH.Timer2OffTime", "Timer 2 Off"),
}


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities = []
    for key, (point, name) in TIME_POINTS.items():
        entities.append(
            IStoreTimeEntity(coordinator, api, key, point, name)
        )

    async_add_entities(entities)


class IStoreTimeEntity(CoordinatorEntity, TimeEntity):
    """Time entity for iStore timer schedule."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator, api, key, point, name):
        super().__init__(coordinator)
        self.api = api
        self.key = key
        self.point = point
        self._attr_name = name
        self._attr_unique_id = f"istore_{api.mdm_id}_{key}"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        """Return the current time value."""
        raw = _get_point_value(self.coordinator, self.api.mdm_id, self.point)
        if raw is None:
            return None

        # Parse HH:MM or HH:MM:SS
        match = re.match(r"(\d{1,2}):(\d{2})", str(raw))
        if match:
            return dt_time(int(match.group(1)), int(match.group(2)))
        return None

    async def async_set_value(self, value):
        """Set a new time value via batch write."""
        time_str = value.strftime("%H:%M")
        try:
            await self.api.async_write_timer_settings(self.coordinator, {self.point: time_str})

            # Optimistically update coordinator cache for instant UI feedback
            mdmid = self.api.mdm_id
            data = self.coordinator.data
            if data and mdmid in data and "points" in data[mdmid]:
                pts = data[mdmid]["points"]
                if self.point in pts:
                    pts[self.point]["value"] = time_str
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set time %s to %s: %s", self.point, time_str, e)
            raise
        finally:
            await asyncio.sleep(COMMAND_REFRESH_DELAY)
            await self.coordinator.async_request_refresh()
