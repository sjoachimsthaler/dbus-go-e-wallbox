# AGENTS.md

## What This Is

A Python D-Bus service that bridges a go-eCharger wallbox (Gemini Flex) to Victron Energy Venus OS. Polls the wallbox REST API every 3s and publishes electrical data on Venus OS D-Bus using the `evcharger` role.

## Single Source of Truth

- **Main script:** `dbus-go-e-wallbox.py` — entire application, single entry point
- **Config:** `config.ini` — wallbox host IP, device instance, name, log level
- **Service scripts:** `install.sh`, `uninstall.sh`, `restart.sh`

## Environment

- **Runtime:** Venus OS (embedded Linux), NOT a standard dev machine
- **Dependency:** `vedbus` is provided by Venus OS at `/opt/victronenergy/dbus-systemcalc-py/ext/velib_python` — **cannot be installed locally**
- **Service supervision:** Runs under Venus OS `svc`. Restart with `svc -t /service/dbus-go-e`
- **Tests:** pytest suite in `tests/` runs locally with `vedbus`/`gi`/`requests` mocked (`tests/conftest.py`): `uv sync --group dev && uv run pytest tests/ -v`. CI runs it on push/PR to `main`. No linter or type checker.

## API Parsing Gotchas

- **`nrg` field** can be either a dict `{U, I, P}` (newer firmware) or a 20-element array (classic API). Script handles both.
- **`car` states:** `1`=idle, `2`=charging, `3`=paused, `4`=complete. Mapped to Victron status: `0`=disconnected, `1`=connected, `2`=charging, `3`=charged.
- **`cdi` field** has two modes based on `cdi.type`:
  - **type 0** (active session): `cdi.value` is a timestamp in ms. Elapsed time = `(rbt - cdi.value) / 1000` seconds.
  - **type 1** (completed session): `cdi.value` is the charging duration in ms. Duration = `cdi.value / 1000` seconds.
- **`wh`** = session energy (Wh). **`eto`** = total lifetime energy (Wh).
- **Current per phase** = max of active phases, NOT sum (single-phase wallbox draws on one phase at a time).

## Key Paths

D-Bus paths follow Victron `evcharger` convention (`/Ac/L1/Voltage`, `/Ac/Energy/Forward`, etc.). Energy published in kWh (`/Ac/Energy/Forward`).

## Testing Changes

Parsing logic is covered by `tests/`; real D-Bus behaviour is only testable on a live Venus OS device. API response fixtures (anonymized — keep them free of serials, MACs, IPs, tokens) live in repo root:
- `api-charging.json` — live charging response
- `api-completed.json` — completed session response
- `api.json` — older charging response (three phases active)
