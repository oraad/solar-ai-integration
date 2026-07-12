# Home Assistant custom integration

Requires **Home Assistant Core 2026.7.0+**.

The [Solar AI Optimizer](https://github.com/oraad/solar-ai-optimizer) HACS integration follows the Home Assistant Integration Quality Scale checklist for HACS custom integrations (not a Core-listed platinum badge). It replaces the legacy [YAML fail-safe package](home-assistant-failsafe.md) with:

- A **pairing code** (standalone) or **Supervisor discovery** (HAOS add-on) so Home Assistant can talk to Solar without pasting tokens
- **Fail-safe watchdog** inside HA (polls Solar `/api/health`)
- An **Update** entity (install available on Docker/Proxmox when self-update is enabled; read-only on the Supervisor add-on)
- Diagnostics, reconfigure / reauth flows, and a repair issue when fail-safe options are incomplete

IndieAuth (Solar → HA) for inverter writes remains available in Solar **Settings**; it is **not** required for the fail-safe or Update entity.

## Solar app vs this integration

This repository is the **HACS integration only**. Install the Solar container or HA Apps add-on from [`oraad/solar-ai-optimizer`](https://github.com/oraad/solar-ai-optimizer).

| Product | Repository | Version |
|---|---|---|
| **Solar app** (Docker / HA Apps) | [oraad/solar-ai-optimizer](https://github.com/oraad/solar-ai-optimizer) | `v0.6.x` |
| **HACS integration** (this repo) | [oraad/solar-ai-integration](https://github.com/oraad/solar-ai-integration) | `v0.2.x` |

- **HA App** — Settings → Apps → add the Solar app repository → install the container ([app setup docs](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)).
- **HACS integration** — this page; fail-safe / Update entity for Docker, Proxmox, or Core.

The integration talks to Solar over HTTP; pair it with an app release **at or above** your last stable app version. App and integration versions do not need to match (e.g. app `0.6.11` + integration `0.1.0`).

## Supported deployments

| Deployment | Fail-safe / health entities | Update entity Install |
|---|---|---|
| Docker / Compose | Yes | Yes when Solar reports `can_apply` |
| Proxmox / container | Yes | Yes when Solar reports `can_apply` |
| Supervisor add-on | Yes | Read-only — update via **Settings → Apps** |

## Install (HACS)

Click to add this repository to HACS (requires [My Home Assistant](https://my.home-assistant.io/) configured in your browser):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=oraad&repository=solar-ai-integration&category=integration)

**Or manually:**

1. HACS → Integrations → Custom repositories → add  
   `https://github.com/oraad/solar-ai-integration` as **Integration** (not Add-on).
2. Install **Solar AI Optimizer**, then restart Home Assistant.

HACS installs from GitHub Releases using `solar_ai_optimizer.zip` (`zip_release` in `hacs.json`). Use the HACS version picker — stable by default; betas selectable.

### Manual install

Copy `custom_components/solar_ai_optimizer/` into your HA `config/custom_components/` directory and restart.

Or download **`solar_ai_optimizer.zip`** from the [integration GitHub Releases](https://github.com/oraad/solar-ai-integration/releases) page and extract so `manifest.json` lands in `config/custom_components/solar_ai_optimizer/`.

### Removal

1. Settings → Devices & services → Solar AI Optimizer → three-dot menu → **Delete**.
2. Optionally remove `config/custom_components/solar_ai_optimizer/` (and restart) if you installed manually or want a clean disk.

## Installation parameters

| Parameter | Required | Description |
|---|---|---|
| Host URL | Yes\* | Base URL Solar is reachable on from HA Core (LAN `http://…:8000`, or Supervisor add-on hostname — **not** the ingress panel URL) |
| Verify SSL | No (default on) | TLS certificate verification |
| Pairing code | Yes\* | One-time `XXXX-XXXX` from Solar Settings (~10 minutes) |
| Grid charge enable | No | Optional `switch` entity for fail-safe |
| Max grid charge current | No | Optional `number` entity for fail-safe amps |
| Stale / debounce seconds | No | Heartbeat freshness and fail-safe debounce (default 120s) |

\* On the **HAOS add-on** path, Supervisor discovery supplies the host and uses `SUPERVISOR_TOKEN` — no URL or pairing code. On standalone / LAN, enter host + pairing code (Zeroconf can pre-fill the host).

## Pair Solar with Home Assistant

### HAOS add-on (recommended)

1. Install the Solar AI Optimizer app from Settings → Apps.
2. When Home Assistant shows a discovery notification for Solar AI Optimizer, confirm it.
3. Done — the integration uses the Supervisor network hostname and `SUPERVISOR_TOKEN` (not stored in the config entry).

### Standalone / Docker / remote

Start the config flow:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solar_ai_optimizer)

**Or:** Settings → Devices & services → Add integration → **Solar AI Optimizer**

1. In the Solar dashboard (admin), open **Settings → Home Assistant connection** and generate a pairing code (or call `POST /api/pair/start` as admin).
2. Note the one-time code (`XXXX-XXXX`, valid ~10 minutes).
3. In the HA config flow, enter the host URL (or accept the Zeroconf-discovered host) and pairing code.
4. Optionally select grid-charge entities and thresholds.

HA stores a minted `sol_c_…` client token in the config entry. Env `API_TOKEN` remains for scripts/MCP only — it is not used for integration setup.

### Add-on networking

When Solar runs as the Supervisor app, prefer the discovery confirm flow above. If configuring manually, use the **direct** add-on HTTP URL on the Supervisor network (slug `solar_ai_optimizer`), not `/api/hassio_ingress/…`. Humans still use the ingress sidebar.

## Configuration options

Open **Configure** on the integration to change fail-safe entities and thresholds. Use **Reconfigure** to change host URL / SSL without re-pairing.

| Option | Description |
|---|---|
| Grid charge enable switch | Turned on when heartbeat is stale beyond debounce |
| Max grid charge current number | Set to max amps from Solar config (or default) |
| Stale seconds | Max age of `heartbeat_last_pulse` before unhealthy |
| Debounce seconds | How long unhealthy must persist before fail-safe latches |

Set **both** fail-safe entities or **neither**. Configuring only one raises a repair issue.

## How data updates

The integration polls Solar every **60 seconds** (`/api/health`, `/api/system/update`, best-effort `/api/config`). While an update install is in progress, polling speeds up to about **2 seconds** for progress.

## Supported functions (entities)

| Platform | Entity | Notes |
|---|---|---|
| binary_sensor | Healthy | Connectivity; on when heartbeat is fresh |
| binary_sensor | Fail-safe active | Diagnostic; on when fail-safe latch is active |
| sensor | Version | Diagnostic |
| sensor | Last pulse | Timestamp diagnostic |
| sensor | Max grid charge current | Diagnostic; amps from Solar config |
| sensor | Install ID | Diagnostic; disabled by default |
| event | Integration activity | Fail-safe activated / cleared events |
| update | Software | Install when `can_apply` and not add-on |

Download diagnostics from the device page (access token redacted).

## Activity

When the fail-safe watchdog acts (Solar heartbeat stale beyond debounce), the integration records activity on the **Solar AI Optimizer** device:

| Signal | What you see |
|---|---|
| **Integration activity** event | `failsafe_activated` with max amps and target entity IDs |
| **Fail-safe active** binary sensor | Turns on when the latch engages |
| **Activity / Logbook** | Human-readable entry, e.g. “Fail-safe: grid charge enabled at 40 A (Solar disconnected)” |

When Solar reconnects (heartbeat fresh again), the latch clears and you see:

| Signal | What you see |
|---|---|
| **Integration activity** event | `failsafe_cleared` |
| **Fail-safe active** binary sensor | Turns off |
| **Activity / Logbook** | “Fail-safe cleared: Solar connection restored” |

Service calls to your configured grid-charge switch and max-current number also appear on those entities’ device pages. The integration does **not** turn off grid charge or restore the previous current when Solar reconnects — Solar resumes optimizer control when it is back online.

## Use cases

1. **Fail-safe grid charge** — When Solar stops pulsing heartbeat (crash, network, outage), the HA watchdog enables a configured grid-charge switch and sets max current so the battery can recover without Solar online.
2. **Software update from HA** — On Docker/Proxmox installs with `can_apply`, use the Update entity (or an automation on `update.solar_ai_optimizer_software`) to install releases without SSH.
3. **Health automations** — Trigger notifications or load-shed when `binary_sensor.solar_ai_optimizer_healthy` turns off for several minutes.

## Fail-safe

The integration owns a **healthy** binary sensor and watchdog:

- Unhealthy = Solar `heartbeat_last_pulse` older than the stale threshold for the debounce duration
- Action: turn on grid-charge enable + set max current (amps from Solar config or default)
- Recovery: latch clears when heartbeat is fresh again; inverter entities are **not** reverted by the integration (see [Activity](#activity))

**Before enabling the integration watchdog**, remove or disable `packages/solar-optimizer-failsafe.yaml` so grid charge is not applied twice.

### Example automation

```yaml
automation:
  - alias: Notify when Solar unhealthy
    triggers:
      - trigger: state
        entity_id: binary_sensor.solar_ai_optimizer_healthy
        to: "off"
        for:
          minutes: 2
    actions:
      - action: notify.persistent_notification
        data:
          title: Solar AI Optimizer unhealthy
          message: Heartbeat stale — fail-safe may enable grid charge.
```

## Software updates

The Update entity always appears. **Install** is offered only when Solar reports `can_apply` (typical Proxmox/Docker with Docker socket). On the Supervisor add-on, update via **Settings → Apps**.

## Known limitations

- Supervisor add-on updates are not applied by the HA Update entity (`can_apply` / deployment = add-on).
- IndieAuth (Solar → HA) for inverter writes is separate from this integration.
- Do not run the legacy YAML fail-safe package together with the integration watchdog.
- Zeroconf discovery pre-fills the Solar host; pairing is still required on standalone installs.

## Troubleshooting

| Symptom | What to try |
|---|---|
| HACS: “add-on repository” / not an integration | Add **`oraad/solar-ai-integration`** as Integration, not the app repo. The app repo (`oraad/solar-ai-optimizer`) is for HA Apps / Docker only. |
| Cannot connect | Check host URL from HA Core network; not ingress URL; firewall / TLS |
| Invalid / expired pairing code | Generate a new code in Solar Settings |
| Unhealthy binary sensor | Confirm Solar heartbeat is writing; raise stale seconds; check HA time sync |
| Unauthorized / reauth | Revoke or expired client — use Reauth with a new pairing code |
| Fail-safe repair issue | Set both switch and number (or clear both) in options |
| Update Install unavailable | Expected on add-on; on Docker ensure self-update / `can_apply` |

## Revoke / reauth

- Solar Settings → revoke a paired client → HA looks like unauthorized until you reauth (new pairing code).
- Rotating env `API_TOKEN` does **not** revoke the HA client token.

## Related

- [Solar app setup](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)
- [Fail-safe (legacy package)](home-assistant-failsafe.md)
- [Roles and access](https://oraad.github.io/solar-ai-optimizer/ingress-auth/)
- [Security](https://oraad.github.io/solar-ai-optimizer/security/)
