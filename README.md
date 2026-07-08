# Solar AI Optimizer — Home Assistant Integration

HACS custom integration for [Solar AI Optimizer](https://github.com/oraad/solar-ai-optimizer): pairing, fail-safe watchdog, Update entity, and diagnostics.

**This repository is only the Home Assistant integration.** Install the Solar app (Docker container or HA Apps add-on) from [`oraad/solar-ai-optimizer`](https://github.com/oraad/solar-ai-optimizer).

## Prerequisites

- [Home Assistant](https://www.home-assistant.io/) Core **2026.7.0+**
- [HACS](https://hacs.xyz/) installed
- Solar app running and reachable from HA Core ([app setup](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/))

## Install (HACS)

Click the button below to add this repository to HACS (requires [My Home Assistant](https://my.home-assistant.io/) configured in your browser):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=oraad&repository=solar-ai-integration&category=integration)

**Or manually:**

1. HACS → Integrations → Custom repositories → add  
   `https://github.com/oraad/solar-ai-integration` as **Integration** (not Add-on).
2. Install **Solar AI Optimizer**, then restart Home Assistant.

HACS installs from GitHub Releases using `solar_ai_optimizer.zip`.

## Configure

After installing and restarting, start the config flow:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=solar_ai_optimizer)

**Or:** Settings → Devices & services → Add integration → **Solar AI Optimizer**

If the integration does not appear, clear your browser cache and restart Home Assistant.

## Pair with Solar

1. In the Solar dashboard, open **Settings → Home Assistant connection** and generate a pairing code.
2. In the HA config flow, enter the Solar host URL and pairing code.

## Documentation

- [Integration guide](https://oraad.github.io/solar-ai-integration/home-assistant-integration/)
- [Fail-safe (legacy YAML)](https://oraad.github.io/solar-ai-integration/home-assistant-failsafe/)
- [Solar app setup](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)

## Migration from monorepo

If you added `oraad/solar-ai-optimizer` as a HACS Integration custom repository, remove it and add **`oraad/solar-ai-integration`** instead. Existing pairing tokens and config entries are preserved when you update files in place.

## Development

```bash
python scripts/sync-version.py --check
bash scripts/package-ha-integration.sh
```

CI runs hassfest, HACS validation, PHCC tests (≥95% coverage), and mypy strict on push/PR.

## License

MIT — see [LICENSE](LICENSE).
