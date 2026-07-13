"""Unit tests for iStore binary sensor is_on logic."""

from unittest.mock import MagicMock

from custom_components.istore_heatpump.binary_sensor import IStoreBinarySensor
from tests.conftest import make_coordinator, make_api


class TestBinarySensorIsOn:
    """Tests for IStoreBinarySensor.is_on across all point types."""

    def test_compressor_on(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.CompressorStatus": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "compressor_status", "PUB_WH.CompressorStatus", "Compressor Status")
        assert sensor.is_on is True

    def test_compressor_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.CompressorStatus": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "compressor_status", "PUB_WH.CompressorStatus", "Compressor Status")
        assert sensor.is_on is False

    def test_booster_on(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.Booster": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "booster_state", "PUB_WH.Booster", "Booster State")
        assert sensor.is_on is True

    def test_booster_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.Booster": {"value": 2}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "booster_state", "PUB_WH.Booster", "Booster State")
        assert sensor.is_on is False

    def test_booster_value_0_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.Booster": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "booster_state", "PUB_WH.Booster", "Booster State")
        assert sensor.is_on is False

    def test_4way_on_int(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.4WayStatus": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "4way_status", "PUB_WH.4WayStatus", "4 Way Valve")
        assert sensor.is_on is True

    def test_4way_on_string(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.4WayStatus": {"value": "1"}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "4way_status", "PUB_WH.4WayStatus", "4 Way Valve")
        assert sensor.is_on is True

    def test_4way_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.4WayStatus": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "4way_status", "PUB_WH.4WayStatus", "4 Way Valve")
        assert sensor.is_on is False

    def test_fan_on(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.FanSpeed": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "fan_status", "PUB_WH.FanSpeed", "Fan Status")
        assert sensor.is_on is True

    def test_fan_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.FanSpeed": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "fan_status", "PUB_WH.FanSpeed", "Fan Status")
        assert sensor.is_on is False

    def test_defrost_on(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.DefrostStatus": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "defrost_status", "PUB_WH.DefrostStatus", "Defrost Status")
        assert sensor.is_on is True

    def test_defrost_off(self):
        coordinator = make_coordinator(points_dict={"PUB_WH.DefrostStatus": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "defrost_status", "PUB_WH.DefrostStatus", "Defrost Status")
        assert sensor.is_on is False

    def test_timer1_on_enabled(self):
        coordinator = make_coordinator(points_dict={"PRI_RE_WH.Timer1On": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "timer1_on", "PRI_RE_WH.Timer1On", "Timer 1 Enabled")
        assert sensor.is_on is True

    def test_timer1_on_disabled(self):
        coordinator = make_coordinator(points_dict={"PRI_RE_WH.Timer1On": {"value": 0}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "timer1_on", "PRI_RE_WH.Timer1On", "Timer 1 Enabled")
        assert sensor.is_on is False

    def test_timer2_on_enabled(self):
        coordinator = make_coordinator(points_dict={"PRI_RE_WH.Timer2On": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "timer2_on", "PRI_RE_WH.Timer2On", "Timer 2 Enabled")
        assert sensor.is_on is True

    def test_no_data_returns_false(self):
        coordinator = MagicMock()
        coordinator.data = None
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "compressor_status", "PUB_WH.CompressorStatus", "Compressor Status")
        assert sensor.is_on is False

    def test_missing_point_returns_false(self):
        coordinator = make_coordinator(points_dict={"OTHER.Point": {"value": 1}})
        api = make_api()
        sensor = IStoreBinarySensor(coordinator, api, "compressor_status", "PUB_WH.CompressorStatus", "Compressor Status")
        assert sensor.is_on is False
