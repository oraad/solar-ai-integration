# Home Assistant fail-safe (heartbeat watchdog)

**Recommended:** install the [HACS custom integration](home-assistant-integration.md)
(Home Assistant **2026.7+**). It polls Solar health and runs the watchdog inside HA —
no YAML package required.

The sections below describe the **legacy YAML package** for older installs. If you use
the integration, **disable this package** to avoid double grid-charge actions.

When the solar-ai-optimizer stops or hangs, Home Assistant can detect a stale
heartbeat and enable grid charge at maximum current — the same resilience
action the optimizer applies on graceful shutdown or via the kill switch.

## Prerequisites

- solar-ai-optimizer connected to Home Assistant (add-on or Docker) — see [Home Assistant setup](home-assistant-setup.md)
- Inverter **write** entities mapped in Settings → Inverter (grid charge enable + max grid charge current)
- Battery **Max grid charge current (A)** set in Settings → Battery

## Step 1 — Import the HA package (legacy)

Enable packages in `configuration.yaml` if needed — see
[Home Assistant setup → Enable packages](home-assistant-setup.md#enable-packages-in-configurationyaml).

Copy [`examples/home-assistant/packages/solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml) into your Home Assistant `config/packages/` directory (or merge into `configuration.yaml`).

The package defines:

| Entity | Purpose |
|--------|---------|
| `input_datetime.solar_optimizer_heartbeat` | Heartbeat timestamp (updated by the optimizer in site-local wall time) |
| `input_number.solar_optimizer_heartbeat_stale_s` | Stale threshold in seconds for the healthy sensor (default 120) |
| `input_number.solar_optimizer_max_grid_charge_a` | Max grid charge current for the fail-safe automation |
| `binary_sensor.solar_optimizer_healthy` | Template sensor (stale if heartbeat &gt; threshold) |

Edit placeholders before reloading:

- `switch.YOUR_GRID_CHARGE_ENTITY` — same as Settings → Inverter → Grid charge enable
- `number.YOUR_MAX_GRID_CHARGE_CURRENT` — same as Settings → Inverter → Max grid charge current
- `input_number.solar_optimizer_max_grid_charge_a` **initial** — match Grid charge → Max grid charge current (A)

Reload helpers, templates, and automations after editing.

## Step 2 — Configure the optimizer

In the dashboard **Settings** → **Fail-safe**:

| Field | Value |
|-------|--------|
| Heartbeat enabled | On |
| Heartbeat entity | `input_datetime.solar_optimizer_heartbeat` (default) |
| Shutdown fail-safe enabled | On (default) |

Set **Settings → Site → Timezone** to match Home Assistant's configured timezone so heartbeat wall clock and the fail-safe template agree.

Save changes.

Verify in **Developer tools** → **States** that `input_datetime.solar_optimizer_heartbeat` updates every control loop interval (default ~30s).

If you already created the helper manually with a different entity ID, set **Heartbeat entity** to match.

## How it works

```text
Package creates     →  input_datetime.solar_optimizer_heartbeat
                      input_number.solar_optimizer_heartbeat_stale_s
Optimizer (alive)   →  pulses heartbeat each control cycle (site-local wall clock)
HA template sensor  →  binary_sensor.solar_optimizer_healthy (as_datetime | as_local age check)
HA automation       →  if unhealthy for 2 min → grid ON + max current
Optimizer shutdown  →  grid ON + max current (before process exits)
Kill switch         →  grid ON + max current + pause + restore sheds
```

### Timezone

The optimizer writes the heartbeat as a **naive site-local** `YYYY-MM-DD HH:MM:SS` string. The template parses it with `as_datetime | as_local` so age is compared against `now()` in Home Assistant's timezone. Align **Settings → Site → Timezone** with HA's timezone setting.

**Existing installs:** merge updates from [`solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml) and reload **Helpers** and **Template** entities.

## Tuning

| Parameter | Suggested | Notes |
|-----------|-----------|--------|
| `input_number.solar_optimizer_heartbeat_stale_s` | 90–120 | ~3–4× default 30s control loop |
| Automation `for:` | 2–3 min | Survives restarts without false triggers |
| `input_number.solar_optimizer_max_grid_charge_a` | Match optimizer grid charge config | HA has no direct read of optimizer settings |

## Limitations

- Heartbeat requires the optimizer process to run and reach Home Assistant.
- Graceful shutdown fail-safe does not run on `kill -9` or power loss — rely on the HA automation for hard crashes.
- The HA automation writes inverter entities directly; it does not call the optimizer API (which may be down).

## Health API

`GET /api/health` includes:

- `heartbeat_configured` — heartbeat entity set and enabled
- `heartbeat_last_pulse` — last successful pulse (site-local ISO timestamp)

Metrics counters: `heartbeat_pulses_total`, `heartbeat_failures`.
