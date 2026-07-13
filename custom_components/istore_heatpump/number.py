from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

TARGET_MIN = "WH.TargetTempMin"
TARGET_MAX = "WH.TargetTempMax"
TARGET_SET = "WH.TargetTemp"


async def async_setup_entry(hass, entry, async_add_entities):
    """Temperature control disabled — may void warranty and damage device."""
    return


# Temperature control entities are retained below for reference.
# They are disabled because adjusting the tank temperature
# outside iStore's tested range (15-62°C) can reduce compressor
# lifespan and dramatically lower COP at high temperatures.
#
# Discussion: https://github.com/kungbernard/istore-ha


class IStoreTargetTemperature(CoordinatorEntity, NumberEntity):
    _attr_name = "iStore Target Temperature"
    _attr_icon = "mdi:thermometer"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_step = 1

    def __init__(self, coordinator, api):
        super().__init__(coordinator)
        self.api = api
        self._attr_unique_id = f"istore_{api.mdm_id}_target_temperature"

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None
        try:
            return data[self.api.mdm_id]["points"][TARGET_SET]["value"]
        except Exception:
            return None

    @property
    def min_value(self):
        data = self.coordinator.data
        if not data:
            return 10
        try:
            return data[self.api.mdm_id]["points"][TARGET_MIN]["value"]
        except Exception:
            return 10

    @property
    def max_value(self):
        data = self.coordinator.data
        if not data:
            return 62
        try:
            return data[self.api.mdm_id]["points"][TARGET_MAX]["value"]
        except Exception:
            return 62

    async def async_set_native_value(self, value: float):
        minv = self.min_value
        maxv = self.max_value
        if not (minv <= value <= maxv):
            raise ValueError(
                f"Target temperature must be between {minv}°C and {maxv}°C"
            )
        # API call omitted — temperature control disabled


class IStoreTargetMin(CoordinatorEntity, NumberEntity):
    _attr_name = "iStore Target Temperature Min"
    _attr_icon = "mdi:thermometer-low"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_step = 1

    def __init__(self, coordinator, api):
        super().__init__(coordinator)
        self.api = api
        self._attr_unique_id = f"istore_{api.mdm_id}_target_temp_min"

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None
        try:
            return data[self.api.mdm_id]["points"][TARGET_MIN]["value"]
        except Exception:
            return None

    @property
    def min_value(self):
        return 10

    @property
    def max_value(self):
        data = self.coordinator.data
        if not data:
            return 75
        try:
            max_temp = data[self.api.mdm_id]["points"][TARGET_MAX]["value"]
            return max_temp - 1
        except Exception:
            return 75

    async def async_set_native_value(self, value: float):
        # API call omitted — temperature control disabled
        pass


class IStoreTargetMax(CoordinatorEntity, NumberEntity):
    _attr_name = "iStore Target Temperature Max"
    _attr_icon = "mdi:thermometer-high"
    _attr_native_unit_of_measurement = "°C"
    _attr_native_step = 1

    def __init__(self, coordinator, api):
        super().__init__(coordinator)
        self.api = api
        self._attr_unique_id = f"istore_{api.mdm_id}_target_temp_max"

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None
        try:
            return data[self.api.mdm_id]["points"][TARGET_MAX]["value"]
        except Exception:
            return None

    @property
    def min_value(self):
        data = self.coordinator.data
        if not data:
            return 10
        try:
            min_temp = data[self.api.mdm_id]["points"][TARGET_MIN]["value"]
            return min_temp + 1
        except Exception:
            return 10

    @property
    def max_value(self):
        return 75

    async def async_set_native_value(self, value: float):
        # API call omitted — temperature control disabled
        pass
