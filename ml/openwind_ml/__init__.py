"""Leakage-safe probabilistic wind-power forecasting for OpenWind."""

__all__ = ["get_meta", "run_forecast"]


def __getattr__(name: str):
    """Avoid importing scikit-learn for lightweight inspection utilities."""
    if name in __all__:
        from .api import get_meta, run_forecast

        return {"get_meta": get_meta, "run_forecast": run_forecast}[name]
    raise AttributeError(name)
