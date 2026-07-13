# iStore Heat Pump Integration Tests

## Unit Tests

Run with plain pytest (no Home Assistant required):

```bash
pytest tests/ -v
```

Requirements:
- Python 3.11+
- `pytest` and `pytest-asyncio`
- `cryptography` (already a dependency of the integration)

```bash
pip install pytest pytest-asyncio
```

All Home Assistant imports are mocked via `tests/conftest.py` at the
`sys.modules` level, so no HA instance or `homeassistant` package is needed.

### Test Structure

| File | What it tests |
|------|--------------|
| `test_api.py` | `_encrypt_password` RSA-OAEP round-trip, `_get_app_id` and `_get_site_id` response parsing |
| `test_sensor.py` | `IStoreStatusSensor` mode mappings, `IStoreRemainingHotWater` stratification model, `IStoreShowerTimeRemaining` mixing calculation, `IStoreTimeEntity` time parsing |
| `test_binary_sensor.py` | `IStoreBinarySensor.is_on` for compressor, booster, 4WayStatus, FanSpeed, DefrostStatus, and timer points |
| `test_device.py` | `IStoreDevice.device_info` attribute mapping (sn, modelId, macCode, name, manufacturer) |

## Integration Tests (Manual)

The full 7-step auth chain and API communication requires a real iStore account
and physical R290 heat pump. These cannot be automated in CI.

### Manual Test Procedure

1. Set up a test Home Assistant instance with the integration configured against a real iStore account
2. Verify all sensors appear and report non-None values
3. Toggle the Power switch — confirm the heat pump responds and the state updates within 12-30 seconds
4. Toggle the Booster switch — confirm it turns on (1) and off (2)
5. Configure timer schedules and verify they are written correctly
6. Test re-authentication by manually invalidating the stored token

### Known Limitations

- The iStore cloud API does not provide a sandbox/test environment
- Rate limiting behavior is undocumented
- The API uses inconsistent success codes (0, 200, 10000) across endpoints
- Some measurement points return strings while others return integers
