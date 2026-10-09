from datetime import datetime, time, timedelta

from astral import Observer
from astral.sun import dawn, dusk

from processor.constants import LATITUDE, LONGITUDE, MAINTENANCE_WINDOW_DISABLED

CACHE_MAX_AGE = timedelta(hours=25)

# (calculated_at, dawn, dusk) in local time
_cache: tuple[datetime, time, time] | None = None


def _parse_coordinate(name: str, value: str | None) -> float:
    try:
        return float(value or "")
    except ValueError:
        raise ValueError(f"{name} env var must be a number, got {value!r}") from None


def _observer() -> Observer:
    return Observer(
        latitude=_parse_coordinate("LATITUDE", LATITUDE),
        longitude=_parse_coordinate("LONGITUDE", LONGITUDE),
    )


def validate_config() -> None:
    """Fail at startup when the maintenance window is enabled but coordinates are missing or invalid."""
    if not MAINTENANCE_WINDOW_DISABLED:
        _observer()


def is_maintenance_window(now: datetime | None = None) -> bool:
    """Check whether the current local time falls between civil dusk and civil dawn.

    Dusk and dawn are calculated for the device location in the system's local timezone
    and cached until the cache is older than CACHE_MAX_AGE.

    Args:
        now: Local datetime to check against. Defaults to the current local time.

    Returns:
        bool: True if within the maintenance window.
    """
    global _cache
    if MAINTENANCE_WINDOW_DISABLED:
        return False
    now = now or datetime.now()
    if _cache is None or now - _cache[0] > CACHE_MAX_AGE:
        observer = _observer()
        tz = datetime.now().astimezone().tzinfo
        _cache = (
            now,
            dawn(observer, now.date(), tzinfo=tz).time(),  # type: ignore[arg-type]
            dusk(observer, now.date(), tzinfo=tz).time(),  # type: ignore[arg-type]
        )
    _, dawn_time, dusk_time = _cache
    current_time = now.time()
    return current_time >= dusk_time or current_time < dawn_time
