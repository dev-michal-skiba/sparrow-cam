from datetime import datetime, time, timedelta
from unittest.mock import MagicMock

import pytest
from astral import Observer

from processor import maintenance_window
from processor.maintenance_window import (
    CACHE_MAX_AGE,
    _observer,
    _parse_coordinate,
    is_maintenance_window,
    validate_config,
)

DAWN = time(5, 0)
DUSK = time(20, 0)


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch):
    """Reset the module-level sun-times cache before and after each test."""
    monkeypatch.setattr(maintenance_window, "_cache", None)
    yield
    monkeypatch.setattr(maintenance_window, "_cache", None)


@pytest.fixture
def enabled(monkeypatch):
    """Enable the maintenance window with valid coordinates."""
    monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", False)
    monkeypatch.setattr(maintenance_window, "LATITUDE", "52.2297")
    monkeypatch.setattr(maintenance_window, "LONGITUDE", "21.0122")


@pytest.fixture
def fake_sun(monkeypatch):
    """Replace astral dawn/dusk with fixed times and return the mocks for call assertions."""
    dawn_mock = MagicMock(side_effect=lambda observer, date, tzinfo: datetime.combine(date, DAWN, tzinfo=tzinfo))
    dusk_mock = MagicMock(side_effect=lambda observer, date, tzinfo: datetime.combine(date, DUSK, tzinfo=tzinfo))
    monkeypatch.setattr(maintenance_window, "dawn", dawn_mock)
    monkeypatch.setattr(maintenance_window, "dusk", dusk_mock)
    return dawn_mock, dusk_mock


class TestParseCoordinate:
    """Test suite for _parse_coordinate."""

    def test_parses_valid_number(self):
        """A numeric string is converted to float."""
        assert _parse_coordinate("LATITUDE", "52.2297") == pytest.approx(52.2297)

    def test_parses_negative_number(self):
        """Negative coordinates are accepted."""
        assert _parse_coordinate("LONGITUDE", "-3.5") == pytest.approx(-3.5)

    def test_none_raises_naming_variable(self):
        """A missing (None) value raises ValueError naming the variable."""
        with pytest.raises(ValueError, match="LATITUDE env var must be a number"):
            _parse_coordinate("LATITUDE", None)

    def test_empty_string_raises_naming_variable(self):
        """An empty value raises ValueError naming the variable."""
        with pytest.raises(ValueError, match="LONGITUDE env var must be a number"):
            _parse_coordinate("LONGITUDE", "")

    def test_non_numeric_raises_naming_variable(self):
        """A non-numeric value raises ValueError naming the variable and the bad value."""
        with pytest.raises(ValueError, match="LATITUDE env var must be a number, got 'north'"):
            _parse_coordinate("LATITUDE", "north")


class TestObserver:
    """Test suite for _observer."""

    def test_builds_observer_from_coordinates(self, enabled):
        """Observer uses LATITUDE and LONGITUDE from config."""
        observer = _observer()

        assert isinstance(observer, Observer)
        assert observer.latitude == pytest.approx(52.2297)
        assert observer.longitude == pytest.approx(21.0122)

    def test_missing_latitude_raises(self, enabled, monkeypatch):
        """Missing LATITUDE raises ValueError naming LATITUDE."""
        monkeypatch.setattr(maintenance_window, "LATITUDE", None)

        with pytest.raises(ValueError, match="LATITUDE"):
            _observer()

    def test_invalid_longitude_raises(self, enabled, monkeypatch):
        """Invalid LONGITUDE raises ValueError naming LONGITUDE."""
        monkeypatch.setattr(maintenance_window, "LONGITUDE", "east")

        with pytest.raises(ValueError, match="LONGITUDE"):
            _observer()


class TestValidateConfig:
    """Test suite for validate_config."""

    def test_disabled_without_coordinates_does_not_raise(self, monkeypatch):
        """When disabled, coordinates are not required."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", True)
        monkeypatch.setattr(maintenance_window, "LATITUDE", None)
        monkeypatch.setattr(maintenance_window, "LONGITUDE", None)

        validate_config()

    def test_disabled_with_invalid_coordinates_does_not_raise(self, monkeypatch):
        """When disabled, invalid coordinates are ignored."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", True)
        monkeypatch.setattr(maintenance_window, "LATITUDE", "abc")
        monkeypatch.setattr(maintenance_window, "LONGITUDE", "")

        validate_config()

    def test_enabled_with_valid_coordinates_does_not_raise(self, enabled):
        """When enabled with valid coordinates, validation passes."""
        validate_config()

    def test_enabled_missing_latitude_raises(self, enabled, monkeypatch):
        """Enabled without LATITUDE raises ValueError naming LATITUDE."""
        monkeypatch.setattr(maintenance_window, "LATITUDE", None)

        with pytest.raises(ValueError, match="LATITUDE"):
            validate_config()

    def test_enabled_missing_longitude_raises(self, enabled, monkeypatch):
        """Enabled without LONGITUDE raises ValueError naming LONGITUDE."""
        monkeypatch.setattr(maintenance_window, "LONGITUDE", None)

        with pytest.raises(ValueError, match="LONGITUDE"):
            validate_config()

    def test_enabled_non_numeric_latitude_raises(self, enabled, monkeypatch):
        """Enabled with non-numeric LATITUDE raises ValueError naming LATITUDE."""
        monkeypatch.setattr(maintenance_window, "LATITUDE", "north")

        with pytest.raises(ValueError, match="LATITUDE env var must be a number"):
            validate_config()


class TestIsMaintenanceWindow:
    """Test suite for is_maintenance_window."""

    def test_disabled_always_false(self, monkeypatch, fake_sun):
        """When disabled, always returns False regardless of time."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", True)
        dawn_mock, dusk_mock = fake_sun

        assert is_maintenance_window(datetime(2024, 6, 1, 0, 0)) is False
        assert is_maintenance_window(datetime(2024, 6, 1, 23, 0)) is False
        assert is_maintenance_window(datetime(2024, 6, 1, 12, 0)) is False
        dawn_mock.assert_not_called()
        dusk_mock.assert_not_called()
        assert maintenance_window._cache is None

    def test_disabled_does_not_require_coordinates(self, monkeypatch):
        """When disabled, missing coordinates do not raise."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", True)
        monkeypatch.setattr(maintenance_window, "LATITUDE", None)
        monkeypatch.setattr(maintenance_window, "LONGITUDE", None)

        assert is_maintenance_window(datetime(2024, 6, 1, 23, 0)) is False

    @pytest.mark.parametrize(
        "moment",
        [
            datetime(2024, 6, 1, 20, 0),  # exactly dusk (inclusive)
            datetime(2024, 6, 1, 23, 30),  # evening
            datetime(2024, 6, 1, 0, 0),  # midnight
            datetime(2024, 6, 1, 4, 59, 59),  # just before dawn
        ],
    )
    def test_inside_window_true(self, enabled, fake_sun, moment):
        """Times from dusk through to before dawn are inside the window."""
        assert is_maintenance_window(moment) is True

    @pytest.mark.parametrize(
        "moment",
        [
            datetime(2024, 6, 1, 5, 0),  # exactly dawn (exclusive)
            datetime(2024, 6, 1, 12, 0),  # midday
            datetime(2024, 6, 1, 19, 59, 59),  # just before dusk
        ],
    )
    def test_outside_window_false(self, enabled, fake_sun, moment):
        """Times from dawn through to before dusk are outside the window."""
        assert is_maintenance_window(moment) is False

    def test_uses_current_time_when_not_provided(self, enabled, fake_sun, monkeypatch):
        """When now is None, the current local time is used."""
        mock_datetime = MagicMock()
        mock_datetime.now.return_value = datetime(2024, 6, 1, 23, 30)
        monkeypatch.setattr(maintenance_window, "datetime", mock_datetime)

        assert is_maintenance_window() is True
        mock_datetime.now.assert_called()

    def test_real_astral_summer_night_and_day(self, enabled):
        """With real astral calculations for Warsaw, 23:30 is in the window and noon is not."""
        assert is_maintenance_window(datetime(2024, 6, 1, 23, 30)) is True
        assert is_maintenance_window(datetime(2024, 6, 1, 12, 0)) is False

    def test_missing_coordinates_raise_when_enabled(self, monkeypatch):
        """Enabled without coordinates raises ValueError naming the missing variable."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", False)
        monkeypatch.setattr(maintenance_window, "LATITUDE", "52.2")
        monkeypatch.setattr(maintenance_window, "LONGITUDE", None)

        with pytest.raises(ValueError, match="LONGITUDE"):
            is_maintenance_window(datetime(2024, 6, 1, 23, 0))

    def test_invalid_coordinates_raise_when_enabled(self, monkeypatch):
        """Enabled with non-numeric LATITUDE raises ValueError naming LATITUDE."""
        monkeypatch.setattr(maintenance_window, "MAINTENANCE_WINDOW_DISABLED", False)
        monkeypatch.setattr(maintenance_window, "LATITUDE", "x")
        monkeypatch.setattr(maintenance_window, "LONGITUDE", "21.0")

        with pytest.raises(ValueError, match="LATITUDE"):
            is_maintenance_window(datetime(2024, 6, 1, 23, 0))


class TestSunTimesCache:
    """Test suite for the dawn/dusk cache behaviour in is_maintenance_window."""

    def test_first_call_populates_cache(self, enabled, fake_sun):
        """The first call calculates dawn and dusk and stores them with the calculation time."""
        now = datetime(2024, 6, 1, 23, 0)

        is_maintenance_window(now)

        assert maintenance_window._cache == (now, DAWN, DUSK)
        assert fake_sun[0].call_count == 1
        assert fake_sun[1].call_count == 1

    def test_reuses_cache_within_max_age(self, enabled, fake_sun):
        """Subsequent calls within CACHE_MAX_AGE do not recalculate."""
        start = datetime(2024, 6, 1, 12, 0)

        is_maintenance_window(start)
        is_maintenance_window(start + timedelta(hours=1))
        is_maintenance_window(start + CACHE_MAX_AGE)  # exactly at the limit is still cached

        assert fake_sun[0].call_count == 1
        assert fake_sun[1].call_count == 1

    def test_recalculates_after_max_age(self, enabled, fake_sun):
        """A call more than CACHE_MAX_AGE after the cache was built recalculates dawn and dusk."""
        start = datetime(2024, 6, 1, 12, 0)
        later = start + CACHE_MAX_AGE + timedelta(seconds=1)

        is_maintenance_window(start)
        is_maintenance_window(later)

        assert fake_sun[0].call_count == 2
        assert fake_sun[1].call_count == 2
        assert maintenance_window._cache[0] == later

    def test_cache_max_age_is_25_hours(self):
        """Cache max age is 25 hours."""
        assert CACHE_MAX_AGE == timedelta(hours=25)

    def test_cached_times_drive_window_decision(self, enabled, monkeypatch):
        """Window decision uses the cached dawn/dusk values, not recomputed ones."""
        monkeypatch.setattr(
            maintenance_window,
            "_cache",
            (datetime(2024, 6, 1, 0, 0), time(6, 0), time(18, 0)),
        )
        dawn_mock = MagicMock()
        monkeypatch.setattr(maintenance_window, "dawn", dawn_mock)

        assert is_maintenance_window(datetime(2024, 6, 1, 19, 0)) is True
        assert is_maintenance_window(datetime(2024, 6, 1, 17, 0)) is False
        dawn_mock.assert_not_called()
