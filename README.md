# Solar AI Optimizer — Home Assistant Integration

HACS custom integration for [Solar AI Optimizer](https://github.com/oraad/solar-ai-optimizer): pairing, fail-safe watchdog, Update entity, and diagnostics.

**This repository is only the Home Assistant integration.** Install the Solar app (Docker container or HA Apps add-on) from [`oraad/solar-ai-optimizer`](https://github.com/oraad/solar-ai-optimizer).

## Install (HACS)

1. HACS → Integrations → Custom repositories → add  
   `https://github.com/oraad/solar-ai-integration` as **Integration** (not Add-on).
2. Install **Solar AI Optimizer**, restart Home Assistant.
3. Settings → Devices & services → Add integration → **Solar AI Optimizer**.

HACS installs from GitHub Releases using `solar_ai_optimizer.zip`.

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
