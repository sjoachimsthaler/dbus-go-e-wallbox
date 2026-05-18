# dbus-go-e-charger
Integrate go-eCharger wallboxes (Gemini Flex, etc.) into [Victron Energy Venus OS](https://github.com/victronenergy/venus)

## Purpose
With the scripts in this repo you can install, uninstall, restart a service that connects your go-eCharger wallbox to the VenusOS / GX devices from Victron Energy. The wallbox phase voltages, currents, powers, charging status and session energy are published via D-Bus so they appear natively in VictronConnect, Venus OS and any system calc.

## Inspiration
This project is based on the following open-source Victron D-Bus plugins – many thanks for sharing the knowledge:
- https://github.com/sjoachimsthaler/dbus-kostal
- https://github.com/RalfZim/venus.dbus-fronius-smartmeter
- https://github.com/victronenergy/dbus-smappee
- https://github.com/fabian-lauer/dbus-shelly-3em-smartmeter
- https://github.com/Louisvdw/dbus-serialbattery

## How it works
### My setup
- go-eCharger Gemini Flex with latest firmware
  - Connected to the local Wi-Fi network
  - IP `192.168.1.XX`
- Victron Energy Multiplus II GX with Venus OS
  - Connected to the same network

### Details / Process
The plugin is inspired by the @sjoachimsthaler dbus-kostal integration.

What the script does:
- Runs as a supervised service under Venus OS
- Connects to the VenusOS D-Bus as `com.victronenergy.evcharger.http_XX`
- After successful D-Bus connection, the go-eCharger REST API v2 is polled – specifically the `/api/status?filter=nrg,eto,se,carconn,current` endpoint
- Serial is read from the device info response
- Paths are added to the D-Bus with default value `0` – including settings like name, role, etc.
- A polling loop fetches wallbox data every 3 seconds and updates the D-Bus values

That's it 😄

## Install & Configuration

### Get the code
Download and extract the repository to `/data/dbus-go-e` on your VenusOS device, then run the install script.

```bash
wget -qO /tmp/dbus-go-e.tar.gz https://github.com/sjoachimsthaler/dbus-go-e-wallbox/archive/refs/heads/main.tar.gz
tar -xzf /tmp/dbus-go-e.tar.gz -C /data
mv /data/dbus-go-e-wallbox-main /data/dbus-go-e
chmod a+x /data/dbus-go-e/install.sh
/data/dbus-go-e/install.sh
```

⚠️ Check the configuration after install – the service is already running and with wrong connection data (host) you will spam the log file.

### Change config.ini
Edit `/data/dbus-go-e/config.ini` – most importantly the `Host` value in the `ONPREMISE` section:

| Section  | Config value   | Explanation                                                       |
|----------|----------------|-------------------------------------------------------------------|
| DEFAULT  | DeviceInstance | Unique instance number on the Victron D-Bus (1-255)               |
| DEFAULT  | CustomName     | Friendly name shown in VictronConnect / Venus OS                   |
| DEFAULT  | LogLevel       | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`                    |
| ONPREMISE| Host           | IP address or hostname of your go-eCharger wallbox (e.g. `192.168.1.XX`) |

> ℹ️ Why `evcharger` role? See [docs/roles.md](docs/roles.md) for an explanation of all available roles and why `evcharger` is the correct choice.

## Update

Download the latest version and overwrite the existing files, then restart the service. Your `config.ini` is preserved.

```bash
wget -qO /tmp/dbus-go-e.tar.gz https://github.com/sjoachimsthaler/dbus-go-e-wallbox/archive/refs/heads/main.tar.gz
tar -xzf /tmp/dbus-go-e.tar.gz -C /tmp
cp /tmp/dbus-go-e-wallbox-main/*.py /data/dbus-go-e/
cp /tmp/dbus-go-e-wallbox-main/*.sh /data/dbus-go-e/
svc -t /service/dbus-go-e
```

The last command sends a TERM signal to the supervised service, which causes it to restart automatically.

## Used documentation
- https://github.com/victronenergy/venus/wiki/dbus#evcharger - D-Bus paths for the Victron namespace EV Charger
- https://github.com/victronenergy/venus/wiki/dbus-api - D-Bus API from Victron
- https://github.com/goecharger/go-eCharger-API-v2 - go-eCharger REST API v2 documentation
- https://www.victronenergy.com/live/ccgx:root_access - How to get root access on GX device / Venus OS

## License
This project is licensed under the GNU General Public License v3.0.
