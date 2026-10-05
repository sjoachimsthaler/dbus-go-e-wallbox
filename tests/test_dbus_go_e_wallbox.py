import json
import os

import pytest

import dbus_go_e_wallbox as m

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def load_fixture(name):
    with open(os.path.join(REPO_ROOT, name)) as f:
        return json.load(f)


def run_update(data, ok=True, requests_error=None):
    """Run DbusGoEWallboxService._update against `data`.

    Returns (published_paths, update_return_value).
    """
    published = {'/UpdateIndex': 0}
    service = m.DbusGoEWallboxService.__new__(m.DbusGoEWallboxService)
    service._dbusservice = published
    service._lastUpdate = 0

    response = m.requests.get.return_value
    response.ok = ok
    response.status_code = 200 if ok else 500
    response.json.return_value = data
    m.requests.get.side_effect = requests_error
    try:
        result = service._update()
    finally:
        m.requests.get.side_effect = None
    return published, result


class TestCharging:
    """api-charging.json: car charging, list-style nrg, cdi type 0."""

    @pytest.fixture
    def published(self):
        return run_update(load_fixture('api-charging.json'))[0]

    def test_voltages(self, published):
        assert published['/Ac/L1/Voltage'] == pytest.approx(225.99, abs=0.01)
        assert published['/Ac/L2/Voltage'] == pytest.approx(230.02, abs=0.01)
        assert published['/Ac/L3/Voltage'] == pytest.approx(234.36, abs=0.01)
        assert published['/Ac/Voltage'] == pytest.approx(230.12, abs=0.01)

    def test_single_phase_current_and_power(self, published):
        assert published['/Ac/L1/Current'] == pytest.approx(5.852, abs=0.001)
        assert published['/Ac/L2/Current'] == 0
        assert published['/Ac/L3/Current'] == 0
        assert published['/Ac/L1/Power'] == pytest.approx(1307.01, abs=0.01)
        assert published['/Ac/Power'] == pytest.approx(1307.01, abs=0.01)

    def test_status_connected_and_charging(self, published):
        assert published['/Status'] == 2
        assert published['/Connected'] == 1

    def test_energy_in_kwh(self, published):
        assert published['/Ac/Energy/Forward'] == pytest.approx(2342.117)
        assert published['/Session/Energy'] == pytest.approx(3.131047, abs=1e-6)

    def test_session_time_is_rbt_minus_cdi(self, published):
        # (85755463 - 81889634) ms
        assert published['/Session/Time'] == 3865

    def test_update_index_incremented(self, published):
        assert published['/UpdateIndex'] == 1


class TestCompleted:
    """api-completed.json: session complete, cdi type 1."""

    @pytest.fixture
    def published(self):
        return run_update(load_fixture('api-completed.json'))[0]

    def test_status_charged(self, published):
        assert published['/Status'] == 3
        assert published['/Connected'] == 1

    def test_session_time_is_cdi_value(self, published):
        assert published['/Session/Time'] == 3740  # 3740228 ms

    def test_no_power(self, published):
        assert published['/Ac/Power'] == 0
        assert published['/Current'] == 0

    def test_session_energy(self, published):
        assert published['/Session/Energy'] == pytest.approx(3.086443, abs=1e-6)


class TestThreePhase:
    """api.json: three phases drawing current."""

    @pytest.fixture
    def published(self):
        return run_update(load_fixture('api.json'))[0]

    def test_current_is_max_of_phases_not_sum(self, published):
        assert published['/Current'] == pytest.approx(5.814, abs=0.001)

    def test_total_current_is_sum(self, published):
        assert published['/Ac/Current'] == pytest.approx(5.814 + 5.624 + 5.776, abs=0.001)

    def test_per_phase_power_and_total(self, published):
        assert published['/Ac/L1/Power'] == pytest.approx(1299.67, abs=0.01)
        assert published['/Ac/L2/Power'] == pytest.approx(1242.13, abs=0.01)
        assert published['/Ac/L3/Power'] == pytest.approx(1304.88, abs=0.01)
        assert published['/Ac/Power'] == pytest.approx(3846.67, abs=0.01)


class TestDictNrg:
    """Newer firmware: nrg is an object {U, I, P}."""

    def test_dict_nrg_is_parsed(self):
        data = {
            'nrg': {'U': [230, 231, 232, 0], 'I': [10, 9, 8], 'P': [2300, 2079, 1856, 0, 6235]},
            'car': 2, 'cdi': {'type': 0, 'value': 0}, 'rbt': 5000,
            'wh': 1500, 'eto': 10000,
        }
        published, _ = run_update(data)
        assert published['/Ac/L2/Voltage'] == 231
        assert published['/Ac/L3/Current'] == 8
        assert published['/Ac/L1/Power'] == 2300
        assert published['/Ac/Power'] == 6235
        assert published['/Current'] == 10


class TestStatusMapping:
    @pytest.mark.parametrize('car, status, connected', [
        (1, 0, 0),  # idle -> disconnected
        (2, 2, 1),  # charging
        (3, 1, 1),  # waiting -> connected
        (4, 3, 1),  # complete -> charged
        (99, 0, 1),  # unknown car state -> disconnected status
    ])
    def test_car_state(self, car, status, connected):
        data = load_fixture('api-charging.json')
        data['car'] = car
        published, _ = run_update(data)
        assert published['/Status'] == status
        assert published['/Connected'] == connected

    def test_idle_has_zero_session_time(self):
        data = load_fixture('api-charging.json')
        data['car'] = 1
        published, _ = run_update(data)
        assert published['/Session/Time'] == 0

    def test_negative_elapsed_time_is_clamped(self):
        data = load_fixture('api-charging.json')
        data['cdi'] = {'type': 0, 'value': data['rbt'] + 10000}
        published, _ = run_update(data)
        assert published['/Session/Time'] == 0


class TestErrorHandling:
    """_update must always return True so the GLib timer keeps running."""

    def test_http_error_publishes_nothing(self):
        published, result = run_update({}, ok=False)
        assert result is True
        assert '/Ac/Power' not in published
        assert published['/UpdateIndex'] == 0

    def test_connection_error(self):
        published, result = run_update({}, requests_error=m.requests.exceptions.ConnectionError('down'))
        assert result is True
        assert '/Ac/Power' not in published
        assert published['/UpdateIndex'] == 1

    def test_timeout(self):
        published, result = run_update({}, requests_error=m.requests.exceptions.Timeout())
        assert result is True
        assert '/Ac/Power' not in published

    def test_missing_nrg_does_not_crash(self):
        data = load_fixture('api-charging.json')
        del data['nrg']
        published, result = run_update(data)
        assert result is True
        assert published['/Ac/Power'] == 0

    def test_null_cdi_does_not_crash(self):
        data = load_fixture('api-charging.json')
        data['cdi'] = None
        published, result = run_update(data)
        assert result is True
        assert '/Session/Time' not in published
        assert published['/UpdateIndex'] == 1

    def test_non_numeric_value_does_not_crash(self):
        data = load_fixture('api-charging.json')
        data['eto'] = 'garbage'
        published, result = run_update(data)
        assert result is True
        assert '/Ac/Energy/Forward' not in published
