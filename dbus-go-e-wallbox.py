#!/usr/bin/env python
# vim: ts=2 sw=2 et

# Normal packages
import platform
import logging
import sys
import os
import time
import requests
import configparser

# Victron packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

# Python 2/3 GLib compatibility
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject


class DbusGoEWallboxService:
    """Victron D-Bus service for go-eCharger wallbox (Gemini Flex).

    Polls the wallbox HTTP API for phase voltages, currents, powers,
    charging status and session energy, then publishes them on
    Victron D-Bus paths under the 'evcharger' role.
    """

    def __init__(self, paths, productname='go-e Charger',
                 connection='go-e http REST API'):
        config = self._getConfig()

        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT'].get('CustomName', 'GoE Wallbox')

        servicename = 'com.victronenergy.evcharger'

        self._dbusservice = VeDbusService(
            "{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d", servicename, deviceinstance)

        # Management objects
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path(
            '/Mgmt/ProcessVersion',
            '1.2.0 running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', 0xA101)  # Generic EV charger
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', 'evcharger')
        self._dbusservice.add_path('/FirmwareVersion', 1.0)
        self._dbusservice.add_path('/Serial', self._getGoESerial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        # Register all D-Bus paths with formatting callbacks
        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path,
                settings['initial'],
                gettextcallback=settings['textformat'],
                writeable=True,
                onchangecallback=self._handlechangedvalue,
            )

        self._lastUpdate = 0

        # Poll every 3 seconds
        gobject.timeout_add(3000, self._update)

    # ---- internal helpers ---------

    def _getGoESerial(self):
        """Fetch device variant from the wallbox and use it as serial id."""
        config = self._getConfig()
        try:
            url = "http://{host}/api/status?filter=var".format(
                host=config['ONPREMISE']['Host'])
            response = requests.get(url, timeout=5)
            if response.ok:
                data = response.json()
                return str(data.get('var', '0'))
        except Exception as exc:
            logging.warning("Could not fetch go-e serial: %s", exc)
        return "UNKNOWN"

    @staticmethod
    def _getConfig():
        config = configparser.RawConfigParser()
        config.read(os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'config.ini'))
        return config

    # ---- main polling loop ------

    def _update(self):
        """Fetch wallbox telemetry and publish to D-Bus."""
        try:
            config = self._getConfig()

            # Fetch the data we need (nrg for phase data, eto for total energy,
            # se for session energy, carconn for connected state,
            # current for actual charging current)
            url = "http://{host}/api/status?filter=nrg,eto,se,carconn,current".format(
                host=config['ONPREMISE']['Host'])
            response = requests.get(url, timeout=5)

            if not response.ok:
                logging.warning(
                    "HTTP %s fetching wallbox data", response.status_code)
                return True

            data = response.json()
            nrg = data.get('nrg', {})

            # Voltages (index 0=L1, 1=L2, 2=L3, 3=N)
            u = nrg.get('U', [0, 0, 0, 0])
            voltage_l1 = float(u[0]) if len(u) > 0 else 0
            voltage_l2 = float(u[1]) if len(u) > 1 else 0
            voltage_l3 = float(u[2]) if len(u) > 2 else 0
            average_voltage = (voltage_l1 + voltage_l2 + voltage_l3) / 3.0

            # Currents (index 0=L1, 1=L2, 2=L3)
            i = nrg.get('I', [0, 0, 0])
            current_l1 = float(i[0]) if len(i) > 0 else 0
            current_l2 = float(i[1]) if len(i) > 1 else 0
            current_l3 = float(i[2]) if len(i) > 2 else 0
            total_current = current_l1 + current_l2 + current_l3

            # Powers (index 0=L1, 1=L2, 2=L3, 3=N, 4=Total)
            p = nrg.get('P', [0, 0, 0, 0, 0])
            power_l1 = abs(float(p[0])) if len(p) > 0 else 0
            power_l2 = abs(float(p[1])) if len(p) > 1 else 0
            power_l3 = abs(float(p[2])) if len(p) > 2 else 0
            total_power = abs(float(p[4])) if len(p) > 4 else 0

            # Total energy in Wh across the lifetime of the device
            total_energy_wh = float(data.get('eto', 0))

            # Session energy in Wh
            session_energy_wh = float(data.get('se', 0))

            # Connected state (carconn: 0=no, 1=yes)
            car_connected = int(data.get('carconn', 0))

            # Actual charging current (amps)
            charging_current = float(data.get('current', 0))

            # Charging status mapping:
            # 0=disconnected, 1=connected, 2=charging, 4=waiting for sun
            # 5=waiting for RFID, 6=waiting for start
            status = 0
            if car_connected == 1:
                if charging_current > 0 or total_power > 0:
                    status = 2  # charging
                else:
                    status = 1  # connected but not charging
            else:
                status = 0  # disconnected

            # Publish to D-Bus
            # Per-phase electrical data
            self._dbusservice['/Ac/L1/Voltage'] = voltage_l1
            self._dbusservice['/Ac/L1/Current'] = current_l1
            self._dbusservice['/Ac/L1/Power'] = power_l1

            self._dbusservice['/Ac/L2/Voltage'] = voltage_l2
            self._dbusservice['/Ac/L2/Current'] = current_l2
            self._dbusservice['/Ac/L2/Power'] = power_l2

            self._dbusservice['/Ac/L3/Voltage'] = voltage_l3
            self._dbusservice['/Ac/L3/Current'] = current_l3
            self._dbusservice['/Ac/L3/Power'] = power_l3

            # Totals
            self._dbusservice['/Ac/Voltage'] = average_voltage
            self._dbusservice['/Ac/Current'] = total_current
            self._dbusservice['/Ac/Power'] = total_power

            # Energy
            self._dbusservice['/Ac/Energy/Forward'] = total_energy_wh / 1000.0

            # EV charger specific paths
            self._dbusservice['/Connected'] = car_connected
            self._dbusservice['/Status'] = status
            self._dbusservice['/Current'] = charging_current
            self._dbusservice['/Session/Energy'] = session_energy_wh / 1000.0
            self._dbusservice['/Session/Time'] = 0  # Not available from go-eCharger API v2

            self._lastUpdate = time.time()

        except requests.exceptions.ConnectionError as exc:
            logging.critical("Cannot reach go-e wallbox: %s", exc)
        except requests.exceptions.Timeout:
            logging.critical("go-e wallbox request timed out")
        except (ValueError, KeyError, TypeError) as exc:
            logging.critical("Parsing error: %s", exc)
        except Exception as exc:
            logging.critical("Unexpected error: %s", exc, exc_info=exc)

        # Notify Victron that values might have changed
        self._dbusservice['/UpdateIndex'] = (
            (self._dbusservice.get('/UpdateIndex', 0) + 1) % 256)
        return True

    @staticmethod
    def _handlechangedvalue(path, value):
        logging.debug("External write on %s -> %s", path, value)
        return True


# ---- logging helpers ------

def _getLogLevel():
    config = configparser.RawConfigParser()
    config.read(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'config.ini'))
    return logging.getLevelName(
        config['DEFAULT'].get('LogLevel', 'INFO'))


def main():
    logging.basicConfig(
        format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=_getLogLevel(),
        handlers=[
            logging.FileHandler(os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'current.log')),
            logging.StreamHandler(),
        ],
    )

    try:
        logging.info("Starting go-e wallbox D-Bus service")

        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)

        # Human-readable formatting callbacks
        _kwh = lambda p, v: "%.2f kWh" % round(v, 2)
        _a   = lambda p, v: "%.1f A" % round(v, 1)
        _w   = lambda p, v: "%.1f W" % round(v, 1)
        _v   = lambda p, v: "%.1f V" % round(v, 1)
        _s   = lambda p, v: "{} sec".format(v)

        GoE_evcharger = DbusGoEWallboxService(
            paths={
                # AC electrical data
                '/Ac/Energy/Forward':  {'initial': 0, 'textformat': _kwh},
                '/Ac/Power':           {'initial': 0, 'textformat': _w},
                '/Ac/Current':         {'initial': 0, 'textformat': _a},
                '/Ac/Voltage':         {'initial': 0, 'textformat': _v},

                '/Ac/L1/Voltage':      {'initial': 0, 'textformat': _v},
                '/Ac/L1/Current':      {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power':        {'initial': 0, 'textformat': _w},

                '/Ac/L2/Voltage':      {'initial': 0, 'textformat': _v},
                '/Ac/L2/Current':      {'initial': 0, 'textformat': _a},
                '/Ac/L2/Power':        {'initial': 0, 'textformat': _w},

                '/Ac/L3/Voltage':      {'initial': 0, 'textformat': _v},
                '/Ac/L3/Current':      {'initial': 0, 'textformat': _a},
                '/Ac/L3/Power':        {'initial': 0, 'textformat': _w},

                # EV charger specific paths (Victron evcharger spec)
                '/Status':             {'initial': 0, 'textformat': lambda p, v: ['disconnected', 'connected', 'charging'][min(v, 2)]},
                '/Current':            {'initial': 0, 'textformat': _a},
                '/Session/Energy':     {'initial': 0, 'textformat': _kwh},
                '/Session/Time':       {'initial': 0, 'textformat': _s},
            },
        )

        logging.info("D-Bus connected – entering main loop")
        mainloop = gobject.MainLoop()
        mainloop.run()

    except Exception as exc:
        logging.critical("Fatal: %s", str(exc), exc_info=exc)


if __name__ == "__main__":
    main()
