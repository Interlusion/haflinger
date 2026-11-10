"""What every test shares."""

from haflinger import _saxon


def pytest_sessionfinish() -> None:
    """Stop the rules' worker before pytest ends: under coverage, it writes its data only when
    it ends, which `coverage combine` reads right after (development guide, CI)."""
    _saxon.clear_caches()
