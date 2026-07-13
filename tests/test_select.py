"""Unit tests for IStoreWorkModeSelect — work mode option mapping."""

import pytest
from unittest.mock import MagicMock

from custom_components.istore_heatpump.select import (
    IStoreWorkModeSelect, WORK_MODES, WORK_MODE_REVERSE,
)
from tests.conftest import make_coordinator, make_api


class TestWorkModeSelect:
    """Tests for IStoreWorkModeSelect.current_option."""

    def test_standby(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 0}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option == "Standby"

    def test_heating(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 1}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option == "Heating"

    def test_eco(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 2}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option == "Eco"

    def test_hybrid(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 3}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option == "Hybrid"

    def test_boost(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 4}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option == "Boost"

    def test_unknown_value_returns_none(self):
        coordinator = make_coordinator(
            points_dict={"PUB_WH.WorkMode": {"value": 99}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option is None

    def test_missing_data_returns_none(self):
        coordinator = MagicMock()
        coordinator.data = None
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option is None

    def test_missing_point_returns_none(self):
        coordinator = make_coordinator(
            points_dict={"OTHER.Point": {"value": 1}}
        )
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity.current_option is None

    def test_options_list_has_five_modes(self):
        coordinator = make_coordinator()
        api = make_api()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity._attr_options == ["Standby", "Heating", "Eco", "Hybrid", "Boost"]
        assert len(entity._attr_options) == 5

    def test_unique_id_pattern(self):
        api = make_api(mdm_id="test-device")
        coordinator = make_coordinator()
        entity = IStoreWorkModeSelect(coordinator, api)
        assert entity._attr_unique_id == "istore_test-device_work_mode_select"


class TestWorkModeMappings:
    """Tests for WORK_MODES and WORK_MODE_REVERSE dicts."""

    def test_all_modes_mapped(self):
        assert len(WORK_MODES) == 5
        assert WORK_MODES["Standby"] == 0
        assert WORK_MODES["Heating"] == 1
        assert WORK_MODES["Eco"] == 2
        assert WORK_MODES["Hybrid"] == 3
        assert WORK_MODES["Boost"] == 4

    def test_reverse_mapping(self):
        assert WORK_MODE_REVERSE[0] == "Standby"
        assert WORK_MODE_REVERSE[1] == "Heating"
        assert WORK_MODE_REVERSE[2] == "Eco"
        assert WORK_MODE_REVERSE[3] == "Hybrid"
        assert WORK_MODE_REVERSE[4] == "Boost"
        assert len(WORK_MODE_REVERSE) == 5

    def test_reverse_mapping_covers_all_forward_keys(self):
        for name, value in WORK_MODES.items():
            assert WORK_MODE_REVERSE[value] == name
