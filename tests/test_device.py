"""Unit tests for IStoreDevice.device_info — DeviceInfo construction from attributes."""

from unittest.mock import MagicMock

from custom_components.istore_heatpump.device import IStoreDevice
from custom_components.istore_heatpump.const import MANUFACTURER, DOMAIN, CONFIG_PAGE


class TestDeviceInfo:
    """Tests for IStoreDevice.device_info property."""

    def make_attrib_data(self, mdm_id="test-mdm-id", **attrs):
        return {"data": {mdm_id: attrs}}

    def test_full_attributes(self):
        api = MagicMock()
        api.mdm_id = "dev-001"
        api.attrib_data = self.make_attrib_data(
            mdm_id="dev-001",
            sn="SN2024-0001",
            modelId="R290-270L",
            macCode="AA:BB:CC:DD:EE:FF",
            name="My Heat Pump",
            manufacturerName="iStore",
        )

        device = IStoreDevice(api, name="iStore Heat Pump")
        info = device.device_info

        assert info.identifiers == {(DOMAIN, "dev-001")}
        assert info.serial_number == "SN2024-0001"
        assert info.model == "R290-270L"
        assert info.name == "My Heat Pump"
        assert info.manufacturer == "iStore"
        assert info.connections is not None
        assert ("mac", "AA:BB:CC:DD:EE:FF") in info.connections
        assert info.configuration_url == CONFIG_PAGE

    def test_minimal_attributes(self):
        api = MagicMock()
        api.mdm_id = "dev-002"
        api.attrib_data = self.make_attrib_data(mdm_id="dev-002", sn="SN-MINIMAL")

        device = IStoreDevice(api, name="iStore Heat Pump")
        info = device.device_info

        assert info.serial_number == "SN-MINIMAL"
        assert info.model is None
        assert info.connections is None
        assert info.manufacturer == MANUFACTURER
        assert info.name == "iStore Heat Pump"

    def test_model_name_fallback(self):
        api = MagicMock()
        api.mdm_id = "dev-003"
        api.attrib_data = self.make_attrib_data(mdm_id="dev-003", modelName="R290 Tank 270L")

        device = IStoreDevice(api)
        info = device.device_info
        assert info.model == "R290 Tank 270L"

    def test_model_id_takes_priority_over_model_name(self):
        api = MagicMock()
        api.mdm_id = "dev-004"
        api.attrib_data = self.make_attrib_data(mdm_id="dev-004", modelId="R290-V2", modelName="R290 Tank 270L")

        device = IStoreDevice(api)
        info = device.device_info
        assert info.model == "R290-V2"

    def test_no_attrib_data(self):
        api = MagicMock()
        api.mdm_id = "dev-005"
        api.attrib_data = None

        device = IStoreDevice(api, name="Fallback Name")
        info = device.device_info

        assert info.identifiers == {(DOMAIN, "dev-005")}
        assert info.serial_number is None
        assert info.model is None
        assert info.name == "Fallback Name"
        assert info.manufacturer == MANUFACTURER
        assert info.connections is None

    def test_attrib_data_missing_data_key(self):
        api = MagicMock()
        api.mdm_id = "dev-006"
        api.attrib_data = {"other": "stuff"}

        device = IStoreDevice(api)
        info = device.device_info

        assert info.model is None
        assert info.serial_number is None

    def test_mdm_id_not_in_attrib_data(self):
        api = MagicMock()
        api.mdm_id = "dev-007"
        api.attrib_data = {"data": {"some-other-device": {"sn": "OTHER", "modelId": "X"}}}

        device = IStoreDevice(api)
        info = device.device_info
        assert info.serial_number is None
        assert info.model is None

    def test_name_from_api_overrides_constructor(self):
        api = MagicMock()
        api.mdm_id = "dev-008"
        api.attrib_data = self.make_attrib_data(mdm_id="dev-008", name="API Device Name")

        device = IStoreDevice(api, name="Constructor Name")
        info = device.device_info
        assert info.name == "API Device Name"

    def test_default_name_when_none_provided(self):
        api = MagicMock()
        api.mdm_id = "dev-009"
        api.attrib_data = self.make_attrib_data(mdm_id="dev-009")

        device = IStoreDevice(api)
        info = device.device_info
        assert info.name == "iStore Heat Pump"
