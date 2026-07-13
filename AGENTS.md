# Project: iStore Heat Pump HA Integration

Evolving fork of [kungbernard/istore-ha](https://github.com/kungbernard/istore-ha) — a Home Assistant custom integration for iStore R290 heat pump water systems.

## Tech Stack

- Python 3.11+ (Home Assistant minimum)
- aiohttp (HTTP client — bundled with HA)
- cryptography >= 42.0.4 (RSA OAEP password encryption)
- voluptuous (config flow validation — bundled with HA)
- pytest + pytest-asyncio (test framework)

## Commands

```
Lint:      ruff check custom_components/istore_heatpump/
Test:      pytest tests/ -v
Syntax:    for f in custom_components/istore_heatpump/*.py; do python3 -m py_compile "$f"; done
CI:        .forgejo/workflows/ci.yml (lint + test + syntax + manifest validation)
```

No build step. Home Assistant custom components are loaded as raw Python from the config directory.

## Project Structure

```
custom_components/istore_heatpump/    ← Integration code (HACS-compliant)
  ├── __init__.py         Entry point, device registration, 6-platform forwarding
  ├── api.py              iStore cloud API client (auth chain, RSA, 401 retry, controls)
  ├── config_flow.py      Setup wizard (username/password → auto-discover device)
  ├── options_flow.py     Post-setup config (thermo calc parameters)
  ├── const.py            Shared constants (DOMAIN, config keys, tank volume, delay, work modes)
  ├── coordinator.py      DataUpdateCoordinator (30s poll interval)
  ├── device.py           HA DeviceInfo from API attributes (serial, MAC, model)
  ├── sensor.py           Temperature sensors, status sensors, thermodynamic calculations
  ├── binary_sensor.py    10 on/off state sensors (compressor, booster, 4-way, etc.)
  ├── switch.py           Power, Booster, Timer 1/2 toggle switches
  ├── select.py           Work mode selector (Standby/Heating/Eco/Hybrid/Boost)
  ├── time.py             Timer schedule HH:MM time inputs
  ├── text.py             Device name editor (synced to iStore portal)
  ├── number.py           Temperature control (DISABLED — warranty + COP risk)
  ├── manifest.json       v2.0.0 metadata, cryptography dependency
  └── strings.json        Config flow UI labels and error messages

tests/                     ← Unit tests (84 tests, 5 files)
  ├── conftest.py         HA module mocking (sys.modules), shared fixtures
  ├── test_api.py         22 tests: RSA round-trip, auth parsing, set_work_mode
  ├── test_sensor.py      26 tests: work modes, stratification, mixing
  ├── test_binary_sensor.py 17 tests: all binary sensor states
  ├── test_device.py      9 tests: DeviceInfo construction
  └── test_select.py      10 tests: work mode select entity

.forgejo/workflows/ci.yml  ← CI pipeline (Forgejo Actions)
docs/decisions/             ← Architecture Decision Records
hacs.json                   ← HACS discovery config
```

## Code Conventions

Follow Home Assistant integration conventions:

- Entity classes: subclass `CoordinatorEntity` + entity type (SensorEntity, SwitchEntity, SelectEntity, etc.)
- Use `_attr_*` properties for entity metadata (HA convention, avoids constructor args)
- `unique_id` pattern: `f"istore_{api.mdm_id}_{entity_key}"`
- All entities attach to device via `self._attr_device_info = api.device_info`
- Import DOMAIN from `.const`, never hardcode the string
- `snake_case` for Python, `ALL_CAPS` for constants
- No commented-out dead code — git has history
- API methods return `None` for missing data, sensors handle `None` gracefully
- Debug logging: log response codes, never full response bodies

Example entity pattern:
```python
class IStoreSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, api, key, name, unit):
        super().__init__(coordinator)
        self._attr_name = name.replace("_", " ").title()
        self._attr_unique_id = f"istore_{api.mdm_id}_{key.lower()}"
        self._attr_device_info = api.device_info

    @property
    def native_value(self):
        data = self.coordinator.data
        if not data:
            return None
        try:
            return data[self.api.mdm_id]["points"][self.key]["value"]
        except Exception:
            return None
```

## Testing Strategy

**Unit tests:** 84 tests with plain pytest + asyncio. HA imports mocked via `sys.modules` in `tests/conftest.py`. No HA runtime required. Run: `pytest tests/ -v`

**Coverage targets:**
- Pure functions (RSA encryption, mode mappings, sensor calculations): 100%
- Auth chain parsing (_get_app_id, _get_site_id): covered via async mocks
- DeviceInfo construction: covered with mock attrib_data
- Select entity: all work mode values, missing/unknown data, round-trip from option to API value
- API control methods: payload construction, error codes, 401 retry

**Not covered (integration-only):**
- Full `authenticate()` 7-step flow (requires real credentials)
- 401 retry and re-authentication (requires HA runtime)
- config_flow.py and options_flow.py (HA Config Flow framework)
- async_setup_entry orchestrators (HA platform setup)

**Manual testing:** Install on live HA instance, verify entities appear, test Power/Booster/Timer controls, check thermodynamic sensor values.

## Boundaries

### Always do:
- Keep temperature control disabled (warranty + COP concerns)
- Encrypt password with RSA-OAEP SHA-256 before transmission
- Auto-refresh session on HTTP 401
- Attach all entities to a HA device (no orphaned entities)
- Log response codes, never full JSON bodies
- Use `self._auth_lock` (asyncio.Lock) for re-authentication

### Ask first:
- Adding new API endpoints or changing the auth chain
- Adding new dependencies beyond `cryptography`
- Enabling temperature control
- Changing poll interval from 30s
- Adding automations that trigger heating decisions

### Never do:
- Log or store passwords in plaintext (they're in HA config entry — that's HA's standard pattern)
- Hardcode tokens or credentials
- Remove the warranty disclaimer
- Disable SSL verification

## Key Architecture Decisions

See `docs/decisions/ADR-001-v2-architecture.md` for full rationale:
1. Base on community PR #11 code (clutrz)
2. Username/password auth with RSA-OAEP encryption
3. Temperature control disabled (warranty + COP)
4. Batch timer writes (individual writes rejected by API)
5. HACS-compliant directory structure
6. CoordinatorEntity pattern for all entities
7. Linear stratification model for thermodynamic sensors
8. Work mode select via `PUB_WH.WorkMode` device control endpoint

## Security

- Password encrypted with RSA-OAEP SHA-256 in transit
- Access token auto-refreshes on 401 with asyncio.Lock preventing races
- Credentials never logged — debug logs show response codes only
- No SSL verification disabled
- Password stored in HA config entry (standard pattern, documented in README)
- Last audit: 2026-06-22 (see commit 211cffe for fixes)

## Upstream

- Original: https://github.com/kungbernard/istore-ha (kungbernard)
- This fork consolidates community PRs #3, #5, #7, #9, #11
- Primary hosting: https://git.drunkrhin0.au/drunkrhin0/istore-ha
