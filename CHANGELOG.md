# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-12

### Added

- Supervisor discovery config flow for HAOS add-on installs (`SUPERVISOR_TOKEN`, no pairing code)
- Zeroconf discovery for standalone / LAN hosts (`_solar-ai._tcp.local.`)
- Auth modes: `supervisor`, `token`, and related API / diagnostics fields

### Changed

- Config flow and docs: pairing remains for standalone; add-on path uses discovery confirm
- Manifest declares `hassio` after-dependency and zeroconf service type

## [0.2.0] - 2026-07-12

### Added

- Integration activity event entity for fail-safe activated / cleared
- Logbook entries when fail-safe latches or clears
- Activity bridge coordinating event, logbook, and fail-safe binary sensor

### Changed

- Fail-safe binary sensor driven via activity latch; docs cover Activity surface

## [0.1.0] - 2026-07-08

### Integration

- Initial release in dedicated `oraad/solar-ai-integration` repository
- HACS IQS Platinum-shaped checklist, diagnostics, reconfigure, repairs, validate-ha CI, zip packaging
- Pairing code flow, fail-safe watchdog, Update entity (Docker/Proxmox when `can_apply`)
- Requires Solar AI Optimizer app **0.6.9+** (HTTP API); app and integration versions are independent
