from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import math

from .const import DOMAIN, TANK_VOLUME_L


def _get_point_value(coordinator, mdm_id, point):
    """Extract a measurement point value from coordinator data, or None."""
    data = coordinator.data
    if not data:
        return None
    try:
        return data[mdm_id]["points"][point]["value"]
    except (KeyError, TypeError):
        return None


def _get_top_bottom(coordinator, mdm_id):
    """Extract top and bottom tank temperatures as floats, or (None, None)."""
    data = coordinator.data
    if not data:
        return None, None
    try:
        points = data[mdm_id]["points"]
        top = float(points["WH.TopTemp"]["value"])
        bottom = float(points["WH.BottomTemp"]["value"])
        return top, bottom
    except (KeyError, TypeError, ValueError):
        return None, None


def _get_tank_volume(api, entry):
    """Return the effective tank volume in liters.

    Priority: options override (>0) > API-discovered value > constant default.
    Set tank_volume to 0 in Options to auto-detect from the API.
    """
    override = entry.options.get("tank_volume", 0)
    if override and override > 0:
        return float(override)
    if api.tank_volume is not None:
        return float(api.tank_volume)
    return TANK_VOLUME_L


def _stratified_fraction(top, bottom, target):
    """Return the tank fraction above target temp using linear stratification.

    bottom <= target <= top  →  interpolated fraction
    target < bottom           →  1.0 (entire tank above target)
    target > top              →  0.0 (no water hot enough)
    top == bottom == target   →  0.0 (no gradient, conservative)

    Callers guard top < target and bottom >= target separately,
    so the top==bottom case is not reached in practice. The function
    handles it defensively if reused elsewhere.
    """
    if target < bottom:
        return 1.0
    if target > top:
        return 0.0
    if top != bottom:
        return (top - target) / (top - bottom)
    return 0.0

SENSORS = {
    "top_temperature": ("WH.TopTemp", "°C"),
    "bottom_temperature": ("WH.BottomTemp", "°C"),
    "target_temperature": ("WH.TargetTemp", "°C"),
    "ambient_temperature": ("PUB_WH.EnvirTemp", "°C"),
    "coil_temperature": ("PUB_WH.CoilTemp", "°C"),
    "suction_temperature": ("PUB_WH.SuctionTemp", "°C"),
    "target_temp_min": ("WH.TargetTempMin", "°C"),
    "target_temp_max": ("WH.TargetTempMax", "°C"),
}

STATUS_SENSORS = {
    # (key, api_point, entity_registry_enabled_default)
    "power_mode": ("WH.OnOff", True),
    "work_mode": ("PUB_WH.WorkMode", False),  # disabled — select entity is superior
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up iStore sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []

    for name, (point, unit) in SENSORS.items():
        entities.append(IStoreSensor(coordinator, api, point, name, unit))

    for name, (point, enabled) in STATUS_SENSORS.items():
        entities.append(IStoreStatusSensor(coordinator, api, point, name, enabled))

    # Thermodynamic calculated sensors
    entities.append(
        IStoreRemainingHotWater(coordinator, api, entry)
    )
    entities.append(
        IStoreRawHotVolume(coordinator, api, entry)
    )
    entities.append(
        IStoreShowerTimeRemaining(coordinator, api, entry)
    )

    async_add_entities(entities)


class IStoreSensor(CoordinatorEntity, SensorEntity):
    """Temperature sensor for iStore heat pump."""

    def __init__(self, coordinator, api, key, name, unit):
        super().__init__(coordinator)
        self.api = api
        self.key = key
        self._attr_name = name.replace("_", " ").title()
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = "temperature"
        self._attr_state_class = "measurement"

        safe_key = key.lower().replace(".", "_")
        safe_name = name.lower()
        self._attr_unique_id = f"istore_{api.mdm_id}_{safe_name}_{safe_key}"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        return _get_point_value(self.coordinator, self.api.mdm_id, self.key)


class IStoreStatusSensor(CoordinatorEntity, SensorEntity):
    """Status sensor with human-readable value mapping."""

    def __init__(self, coordinator, api, key, name, enabled=True):
        super().__init__(coordinator)
        self.api = api
        self.key = key
        self._attr_name = name.replace("_", " ").title()

        safe_key = key.lower().replace(".", "_")
        safe_name = name.lower()
        self._attr_unique_id = f"istore_{api.mdm_id}_{safe_name}_{safe_key}"
        self._attr_device_info = api.device_info
        self._attr_entity_registry_enabled_default = enabled

    @property
    def native_value(self):
        value = _get_point_value(self.coordinator, self.api.mdm_id, self.key)
        if value is None:
            return None

        if self.key == "WH.OnOff":
            return "On" if value == 1 else "Off"

        if self.key == "PUB_WH.WorkMode":
            modes = {0: "Standby", 1: "Heating", 2: "Eco", 3: "Hybrid", 4: "Boost"}
            return modes.get(value, str(value))

        return value


class IStoreRemainingHotWater(CoordinatorEntity, SensorEntity):
    """Estimated remaining hot water volume at tempering temperature."""

    _attr_name = "Remaining Hot Water at Tempering Temp"
    _attr_native_unit_of_measurement = "L"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:water-thermometer"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self._entry = entry
        self._attr_unique_id = f"istore_{api.mdm_id}_remaining_hot_water"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        top, bottom = _get_top_bottom(self.coordinator, self.api.mdm_id)
        if top is None:
            return None

        # Guard against NaN/inf from faulty sensors
        if not (math.isfinite(top) and math.isfinite(bottom)):
            return None

        try:
            cold = float(self._entry.options.get("cold_water_temp", 15))
            tempering = float(self._entry.options.get("tempering_temp", 50))
            tank_volume = _get_tank_volume(self.api, self._entry)
        except (ValueError, TypeError):
            return None

        if tempering <= cold:
            return 0.0

        if not math.isfinite(tank_volume) or tank_volume <= 0:
            return None

        avg_temp = (top + bottom) / 2.0

        if top < tempering:
            return 0.0

        if bottom >= tempering:
            # Whole tank above tempering — all water can be tempered
            liters = tank_volume * (avg_temp - cold) / (tempering - cold)
        else:
            # Stratified: fraction of tank above tempering, with mixing
            y = _stratified_fraction(top, bottom, tempering)
            hot_avg = (top + tempering) / 2.0
            liters = tank_volume * y * (hot_avg - cold) / (tempering - cold)

        result = round(max(0.0, liters), 1)
        return result if math.isfinite(result) else None


class IStoreRawHotVolume(CoordinatorEntity, SensorEntity):
    """Volume of water physically above tempering temperature in the tank.

    Unlike the tempered output sensor, this does NOT include mixing
    with cold water. It is the actual volume of hot water available
    for dilution.
    """

    _attr_name = "Raw Hot Volume Above Tempering Temp"
    _attr_native_unit_of_measurement = "L"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:thermometer-water"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self._entry = entry
        self._attr_unique_id = f"istore_{api.mdm_id}_raw_hot_volume"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        top, bottom = _get_top_bottom(self.coordinator, self.api.mdm_id)
        if top is None:
            return None

        if not (math.isfinite(top) and math.isfinite(bottom)):
            return None

        try:
            tempering = float(self._entry.options.get("tempering_temp", 50))
            tank_volume = _get_tank_volume(self.api, self._entry)
        except (ValueError, TypeError):
            return None

        if not math.isfinite(tank_volume) or tank_volume <= 0:
            return None

        if bottom >= tempering:
            result = tank_volume
        elif top < tempering:
            result = 0.0
        else:
            y = _stratified_fraction(top, bottom, tempering)
            result = y * tank_volume

        return round(max(0.0, result), 1)


class IStoreShowerTimeRemaining(CoordinatorEntity, SensorEntity):
    """Estimated continuous shower minutes remaining at configured shower temp."""

    _attr_name = "Estimated Shower Time Remaining"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = "measurement"
    _attr_icon = "mdi:shower-head"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator)
        self.api = api
        self._entry = entry
        self._attr_unique_id = f"istore_{api.mdm_id}_shower_time"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        top, bottom = _get_top_bottom(self.coordinator, self.api.mdm_id)
        if top is None:
            return None

        if not (math.isfinite(top) and math.isfinite(bottom)):
            return None

        try:
            cold = float(self._entry.options.get("cold_water_temp", 15))
            shower_temp = float(self._entry.options.get("shower_temp", 40))
            flow_rate = float(self._entry.options.get("shower_flow_rate", 9.0))
            tank_volume = _get_tank_volume(self.api, self._entry)
        except (ValueError, TypeError):
            return None

        if shower_temp <= cold:
            return 0.0

        if not math.isfinite(tank_volume) or tank_volume <= 0:
            return None

        if flow_rate <= 0 or top < shower_temp:
            return 0.0

        avg_temp = (top + bottom) / 2.0

        if bottom >= shower_temp:
            minutes = (tank_volume * (avg_temp - cold)) / (flow_rate * (shower_temp - cold))
        else:
            y = _stratified_fraction(top, bottom, shower_temp)
            hot_avg = (top + shower_temp) / 2.0
            minutes = (tank_volume * y * (hot_avg - cold)) / (flow_rate * (shower_temp - cold))

        result = round(max(0.0, minutes), 1)
        return result if math.isfinite(result) else None
