# Home Assistant fail-safe (heartbeat watchdog)

**Recommended:** install the [HACS custom integration](home-assistant-integration.md)
(Home Assistant **2026.7+**). It polls Solar `GET /api/health` (`heartbeat_last_pulse`)
and runs the watchdog inside HA — no YAML package and no Solar heartbeat helper entity.

Solar advances `heartbeat_last_pulse` in-process each control cycle. Settings → Safety
only configures **shutdown** grid-charge-at-max (graceful process exit), not an HA
`input_datetime` pulse.

When Solar stops or hangs, Home Assistant can detect a stale API pulse and enable
grid charge at maximum current — the same resilience action Solar applies on
graceful shutdown or via the kill switch.

## Prerequisites

- solar-ai-optimizer reachable from Home Assistant — see [Home Assistant setup](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)
- HACS integration paired (or Supervisor discovery on HAOS add-on)
- For latching fail-safe: inverter **grid charge enable** switch + **max current** number in integration options
- Battery / grid charge max amps configured in Solar (used when the watchdog latches)

## Configure the HACS watchdog

Open **Configure** on the Solar AI Optimizer integration:

| Option | Purpose |
|--------|---------|
| Grid charge enable switch | Turned on when heartbeat is stale beyond debounce |
| Max grid charge current | Number entity set to Solar’s max grid charge amps |
| Stale seconds | Max age of `heartbeat_last_pulse` before unhealthy (default 120) |
| Debounce seconds | How long unhealthy must persist before latch (default 120) |

Set **both** fail-safe entities or **neither**. See [Home Assistant integration](home-assistant-integration.md).

Verify Solar is cycling: `GET /api/health` should show a recent `heartbeat_last_pulse`,
and the integration **Healthy** binary sensor should stay on.

## How it works (HACS)

```text
Solar control cycle  →  advances heartbeat_last_pulse (in-process)
HACS polls /api/health →  Healthy binary sensor / fail-safe watchdog
Unhealthy + debounce →  switch.turn_on + number.set_value (max amps)
Solar graceful stop  →  grid ON + max current (Settings → Safety shutdown fail-safe)
Kill switch          →  grid ON + max current + pause + restore sheds
```

## Legacy YAML package (do not use with HACS)

Older installs may still have
[`solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml).
That package watched `input_datetime.solar_optimizer_heartbeat`, which **current Solar
builds no longer write**. Disable the package when using the HACS integration to avoid
double grid-charge actions. New installs should not import it.

## Limitations

- API heartbeat requires the Solar process to run and answer `/api/health`.
- Graceful shutdown fail-safe does not run on `kill -9` or power loss — rely on the HACS watchdog for hard crashes.
- The HACS watchdog writes inverter entities directly; it does not call the Solar API for those writes (Solar may be down).

## Health API

`GET /api/health` includes:

- `heartbeat_configured` — always `true` on current builds (liveness is in-process)
- `heartbeat_last_pulse` — last control-cycle pulse (site-local ISO timestamp)

Metrics counters: `heartbeat_pulses_total`, `heartbeat_failures`.
