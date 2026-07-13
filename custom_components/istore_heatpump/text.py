from homeassistant.components.text import TextEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities = [IStoreDeviceName(coordinator, api)]
    async_add_entities(entities)


class IStoreDeviceName(CoordinatorEntity, TextEntity):
    """Text entity to edit the iStore device name."""

    _attr_icon = "mdi:rename-box"
    _attr_name = "Device Name"
    _attr_native_max = 64

    def __init__(self, coordinator, api):
        super().__init__(coordinator)
        self.api = api
        self._attr_unique_id = f"istore_{api.mdm_id}_device_name"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        """Return the current device name."""
        data = self.coordinator.data
        if not data:
            return None

        # Try attrib_data first
        attrib_data = getattr(self.api, "attrib_data", None)
        if attrib_data and "data" in attrib_data:
            device_attrs = attrib_data["data"].get(self.api.mdm_id, {})
            if device_attrs.get("name"):
                return device_attrs["name"]

        # Fallback to arch_data
        arch_data = getattr(self.api, "arch_data", None)
        if arch_data and "data" in arch_data:
            site_data = arch_data["data"].get(self.api.parent_id, {})
            for obj in site_data.get("mdmObjects", {}).get("Res_WaterHeater", []):
                if obj.get("mdmId") == self.api.mdm_id:
                    return obj.get("name", "iStore Heat Pump")

        return "iStore Heat Pump"

    async def async_set_value(self, value: str):
        """Set a new device name on the iStore server and update HA device registry."""
        await self.api.update_asset_name(value)

        # Update the device registry name
        device_registry = async_get_device_registry(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.api.mdm_id)}
        )
        if device:
            device_registry.async_update_device(device.id, name=value)

        # Trigger a coordinator refresh to pick up the name change
        await self.coordinator.async_request_refresh()
