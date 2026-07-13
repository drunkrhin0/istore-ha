# ADR-001: iStore HA Integration v2 Architecture

## Status
Accepted (v2.0.0 shipped, security audited, under maintenance)

## Date
2026-06-22

## Context

The upstream iStore Home Assistant integration (kungbernard/istore-ha, v1.0.0) had several limitations:
- Manual token extraction (7-step browser devtools process)
- No HA device definition (orphaned entities)
- No timer controls (read-only sensors)
- No HACS compliance
- Temperature control enabled, raising warranty concerns

Five community PRs addressed these issues independently (#3 device definition, #5 timer controls, #7 auth, #9 HACS, #11 consolidation), but none were merged upstream. The repo owner had been inactive since January 2026.

We forked to build a consolidated v2.0.0 incorporating the best work from all PRs.

## Decisions

### D-1: Base on PR #11 code

PR #11 (by clutrz, June 2026) was the most comprehensive — it incorporated and fixed work from PRs #3, #5, #7, and #9. It had been reviewed and approved by VeneficusMortis (whose PRs it incorporated). Starting from PR #11's code avoided re-solving problems already addressed by the community.

**Alternatives considered:**
- Build from scratch: would duplicate effort, risk repeating known bugs
- Merge individual PRs: dependency conflicts between PRs would make this fragile
- Wait for upstream: upstream is inactive, indefinite delay

### D-2: Username/password auth with RSA encryption

Replaced the 3-field config form (access_token, parent_id, mdm_id) with a username/password form. The integration runs a 7-step auth chain at setup:

1. GET public key from iStore API
2. RSA-OAEP SHA-256 encrypt password
3. POST login → access_token + org_id
4. POST set-session → company_id
5. GET app resource list → Univers_EMS app_id
6. POST asset tree → site_id (parent_id)
7. POST asset hierarchy → mdm_id (device ID)

Credentials derived from steps 6-7 are stored in the config entry alongside username/password so they survive restarts without re-auth. On HTTP 401 from any API call, the integration re-runs the full auth chain automatically.

**Dependency:** cryptography >= 41.0.0 (RSA OAEP implementation). This is the only external dependency beyond HA core.

### D-3: Temperature control disabled

The v1 integration allowed setting tank target temperature (10-75°C). The upstream maintainer disabled this in their final commit citing warranty concerns. iStore engineer Karl Jensen confirmed:

- Operating above 62°C is outside tested range
- COP drops from ~8.5 at low temps to ~1 at high 60s-70s
- "Running it to over 80°C will likely kill the machine in short order"

The tempering valve (mandated by Australian standards) sets delivered water to 50°C. Adjusting tank setpoint within 60-62°C makes zero difference to tap temperature. The primary value of Home Assistant integration is smart scheduling (time-of-day, solar-aware, ambient temperature-aware heating), not temperature overrides.

The `number.py` platform is retained with `async_setup_entry` returning immediately. The entity classes remain as reference code behind the guard.

### D-4: Batch timer writes

The iStore API's `/device/control` endpoint accepts an array of control commands. Individual writes for each timer parameter (9 separate points: Timer1/2 On/Off/OnTime/OffTime + WorkMode) were rejected by the backend (confirmed in PR #11 testing).

The solution: `async_write_timer_settings()` reads all current timer values from the coordinator, applies only the changed field, and sends the complete schedule as a single batch payload. This mimics the web portal's behavior.

### D-5: HACS-compliant structure

Moved integration code from `istore_heatpump/` to `custom_components/istore_heatpump/` and added `hacs.json` at repo root. This matches HACS's expected layout for integration-type repositories.

The `manifest.json` `platforms` key was removed — it's deprecated in modern HA in favor of `async_forward_entry_setups`.

### D-6: Entity architecture

All entities follow the same pattern:
- Subclass `CoordinatorEntity` + entity type (SensorEntity, SwitchEntity, etc.)
- Read state from `self.coordinator.data[self.api.mdm_id]["points"][self.key]`
- Use `self._attr_device_info = api.device_info` for device registry attachment
- Unique IDs follow pattern: `istore_{mdm_id}_{entity_key}`

Platform split:
| File | Entities |
|------|----------|
| sensor.py | 8 temperature sensors, 2 status sensors, 2 thermodynamic sensors |
| binary_sensor.py | 10 on/off state sensors |
| switch.py | Power, Booster, Timer 1, Timer 2 |
| select.py | Work mode selector (Standby/Heating/Eco/Hybrid/Boost) |
| time.py | 4 timer schedule time inputs |
| text.py | Device name editor |
| number.py | Disabled temperature controls |

### D-8: Work mode select entity

The iStore API exposes work mode via `PUB_WH.WorkMode` as a measurement point (read) and via the `/device/control` endpoint (write). Five modes are supported: Standby (0), Heating (1), Eco (2), Hybrid (3), Boost (4).

A `SelectEntity` provides a dropdown in the HA UI. Mode change commands are sent via `async_write_timer_settings()` as part of a batch write that includes the full timer schedule — the API requires all timer points and the work mode to be written together.

The work mode mapping lives in `select.py` as a bidirectional pair (`WORK_MODES`, `WORK_MODE_REVERSE`) — the single source of truth used by both the status display sensor and the select entity.

### D-7: Thermodynamic sensors

Two calculated sensors estimate hot water availability:

**Remaining Hot Water**: Uses a linear thermal stratification model based on top/bottom temperature sensors. Rather than assuming the tank is fully mixed (which would give optimistic estimates), it calculates the height fraction of water above the target tempering temperature:

```
if bottom ≤ target ≤ top:  y = (top - target) / (top - bottom)
elif target < bottom:      y = 1.0  (entire tank above target)
else:                      y = 0.0  (no water hot enough)
remaining = y × tank_volume (270L for R290)
```

**Estimated Shower Time**: Applies a mixing ratio to the usable volume: `(avg_hot - cold) / (shower_temp - cold)`, then divides by flow rate to get minutes.

Both sensors are configurable via the Options Flow (cold water temp, shower flow rate, comfort temp, tempering temp).

### D-9: Entity defaults — disable redundant sensors

The iStore integration registers 10 binary sensors. Five of them are redundant:
- `compressor_status` duplicates `running_state` (same API point)
- `timer_1_enabled` / `timer_1_disabled` are redundant with `switch.istore_timer_1`
- `timer_2_enabled` / `timer_2_disabled` are redundant with `switch.istore_timer_2`

Similarly, `sensor.istore_work_mode` is read-only while `select.istore_work_mode` shows the same value AND allows changing it.

**Decision:** Set `_attr_entity_registry_enabled_default = False` on these 6 entities. They remain accessible in Settings → Entities (filter "disabled") for users who want them.

> **Note (July 2026):** Timer time inputs (`time.istore_timer_*_time`) were originally disabled by default but re-enabled in v2.1 — the iStore vendor app surfaces timer schedule configuration, so these should be visible by default. The timer-related *binary sensors* (enabled/disabled states) remain disabled as they are redundant with the timer switches.

### D-10: Dual thermo sensors — raw volume and tempered output

Users asked "why do I have 232.7L of remaining hot water on a 180L tank?" The answer: the existing sensor shows tempered output (includes cold water dilution), not raw hot water volume.

**Decision:** Keep both sensors:
- `sensor.istore_raw_hot_volume_above_tempering_temp`: Volume of water physically above tempering temperature. Shows 180L when entire tank is hot. No mixing.
- `sensor.istore_remaining_hot_water_at_tempering_temp`: Tempered output after diluting with cold water. Shows 232.7L because hot water mixed with cold produces more tempered output.

The raw volume is what most users intuitively expect. The tempered output is the "how much shower water can I actually produce" metric. Both are useful for different automation scenarios.

## Consequences

- **Positive:** Setup simplified from 7 manual steps to entering username/password
- **Positive:** All entities now appear under a single device with serial/MAC info
- **Positive:** HACS installable — no manual file copying needed
- **Positive:** Timer scheduling works via batch API (was broken in individual-write approach)
- **Positive:** 113 unit tests (as of v2.1) with pytest + pytest-asyncio; CI pipeline on Forgejo Actions
- **Risk:** `cryptography` dependency is new — must be available on user's HA instance
- **Risk:** iStore API is undocumented and may change — auth chain is fragile to API changes
