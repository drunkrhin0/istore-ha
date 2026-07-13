from __future__ import annotations

import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .api import iStoreApi
from .coordinator import iStoreCoordinator
from .const import (DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_ACCESS_TOKEN, CONF_PARENT_ID, CONF_MDM_ID, TANK_VOLUME_L)
from .device import IStoreDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "binary_sensor", "text", "time", "select"]


def _parse_tank_volume(attrib_data, mdm_id, model_name=None):
    """Extract tank volume in liters from attribute data.

    Tries direct capacity attributes first, then model name regex.
    Returns int if found, None if not.
    Only accepts capacity values in the plausible range 50-500L.
    """
    if attrib_data and "data" in attrib_data:
        attrs = attrib_data["data"].get(mdm_id, {})

        # Try direct capacity attributes — reject values outside plausible range
        for key in ("capacity", "ratedCapacity", "tankVolume", "modelCapacity"):
            val = attrs.get(key)
            if val is not None:
                try:
                    vol = int(float(val))
                    if 50 <= vol <= 500:
                        return vol
                except (ValueError, TypeError):
                    pass

    # Try model name pattern (e.g., "R290-270L", "340L", "270")
    if model_name:
        match = re.search(r"(\d+)\s*L?", str(model_name), re.IGNORECASE)
        if match:
            vol = int(match.group(1))
            if 50 <= vol <= 500:
                return vol

    return None



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up iStore Heat Pump."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    access_token = entry.data[CONF_ACCESS_TOKEN]
    parent_id = entry.data[CONF_PARENT_ID]
    mdm_id = entry.data[CONF_MDM_ID]

    api = iStoreApi(username, password, access_token, parent_id, mdm_id, hass)

    # Fetch device details for DeviceInfo
    try:
        api.arch_data = await api.get_architecture()
    except Exception as e:
        _LOGGER.warning("Failed to fetch architecture for DeviceInfo: %s", e)
        api.arch_data = None

    try:
        api.attrib_data = await api.get_attributes()
    except Exception as e:
        _LOGGER.warning("Failed to fetch attributes for DeviceInfo: %s", e)
        api.attrib_data = None

    # Initialize device helper
    istore_device = IStoreDevice(api)
    api.device_info = istore_device.device_info

    # Discover tank volume from API attributes
    model_name = None
    if api.attrib_data and "data" in api.attrib_data:
        model_name = (
            api.attrib_data["data"]
            .get(api.mdm_id, {})
            .get("modelName")
            or api.attrib_data["data"]
            .get(api.mdm_id, {})
            .get("modelId")
        )
    api.tank_volume = _parse_tank_volume(api.attrib_data, api.mdm_id, model_name)
    if api.tank_volume:
        _LOGGER.info("iStore: discovered tank volume: %s L", api.tank_volume)
    else:
        _LOGGER.info("iStore: could not discover tank volume, defaulting to %s L", TANK_VOLUME_L)

    coordinator = iStoreCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device": istore_device,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.warning(
        "Cannot migrate config entry from version %s to 2. "
        "The new version requires your iStore username and password. "
        "Please delete and re-add the integration.",
        config_entry.version,
    )
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload iStore."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)["api"]
        await api.close()
    return unload_ok
