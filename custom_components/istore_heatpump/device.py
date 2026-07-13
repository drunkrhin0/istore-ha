from homeassistant.helpers.device_registry import DeviceInfo, CONNECTION_NETWORK_MAC, format_mac
from .const import DOMAIN, MANUFACTURER, CONFIG_PAGE
import logging

_LOGGER = logging.getLogger(__name__)


class IStoreDevice:
    """Wrapper that returns DeviceInfo for the heat pump."""

    def __init__(self, api, name: str = None):
        self.api = api
        self.name = name or "iStore Heat Pump"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        name = self.name
        model_id = None
        serial_number = None
        manufacturer = MANUFACTURER
        connections = None

        attrib_data = getattr(self.api, "attrib_data", None)

        if attrib_data and "data" in attrib_data:
            attr_struct = attrib_data["data"]
            mdm_id = self.api.mdm_id

            if mdm_id in attr_struct:
                device_attrs = attr_struct[mdm_id]

                if device_attrs.get("sn"):
                    serial_number = device_attrs["sn"]

                if device_attrs.get("name"):
                    name = device_attrs["name"]

                if device_attrs.get("modelId"):
                    model_id = device_attrs["modelId"]
                elif device_attrs.get("modelName"):
                    model_id = device_attrs["modelName"]

                if device_attrs.get("manufacturerName"):
                    manufacturer = device_attrs["manufacturerName"]

                if device_attrs.get("macCode"):
                    try:
                        formatted_mac = format_mac(device_attrs["macCode"])
                        connections = {(CONNECTION_NETWORK_MAC, formatted_mac)}
                    except Exception:
                        pass

        return DeviceInfo(
            identifiers={(DOMAIN, self.api.mdm_id)},
            manufacturer=manufacturer,
            name=name,
            model=model_id,
            serial_number=serial_number,
            connections=connections,
            configuration_url=CONFIG_PAGE,
        )
