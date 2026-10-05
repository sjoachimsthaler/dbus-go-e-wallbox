"""Mock vedbus/VeDbusService so the module can be imported without Venus OS."""
import sys
from unittest.mock import MagicMock, patch
import types

mock_ve_dbus_service = MagicMock()

# Create a mock vedbus module and patch sys.modules before any other import
vebus_mod = types.ModuleType('vedbus')
vebus_mod.VeDbusService = mock_ve_dbus_service
sys.modules['vedbus'] = vebus_mod

# Also ensure gi.repository.GLib exists
GLib = MagicMock()
GLib.timeout_add = MagicMock(return_value=True)
glib_mod = types.ModuleType('gi.repository.GLib')
glib_mod.GLib = GLib
glib_mod.timeout_add = GLib.timeout_add
gi_mod = types.ModuleType('gi.repository')
gi_mod.GLib = glib_mod
gi_mod.timeout_add = GLib.timeout_add
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = gi_mod
sys.modules['gi.repository.GLib'] = glib_mod

# Now mock requests
mock_requests = MagicMock()
# Real exception classes so the script's `except requests.exceptions.X` clauses work
mock_requests.exceptions.ConnectionError = type('ConnectionError', (Exception,), {})
mock_requests.exceptions.Timeout = type('Timeout', (Exception,), {})
sys.modules['requests'] = mock_requests

# The script has hyphens in its name, so it can't be imported normally.
# Load it by path and expose it as `dbus_go_e_wallbox`.
import importlib.util
import os

_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dbus-go-e-wallbox.py')
_spec = importlib.util.spec_from_file_location('dbus_go_e_wallbox', _script)
_module = importlib.util.module_from_spec(_spec)
sys.modules['dbus_go_e_wallbox'] = _module
_spec.loader.exec_module(_module)
