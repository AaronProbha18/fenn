from pathlib import Path

from whenever import Instant


def copy_template(source: Path, destination: Path) -> None:
    with open(source, "r") as f:
        template = f.read()
    destination.write_text(template)


def _isoformat_utc_now() -> str:
    """Return the current UTC time in ISO 8601 format with microseconds and a +00:00 offset using `whenever`."""
    offset_dt = Instant.now().to_fixed_offset(0)
    microsecond = offset_dt.nanosecond // 1000
    base = offset_dt.format("YYYY-MM-DD'T'hh:mm:ss")
    if microsecond:
        base += f".{microsecond:06d}"
    return base + "+00:00"
