"""Select the real ML package only when it is explicitly ready; otherwise use stable mocks."""
from __future__ import annotations

from .settings import settings

if not settings.use_ml_stub:
    try:  # pragma: no cover - exercised during integration with Person A's package
        from samal_ml import api as ml  # type: ignore
        USING_STUB = False
    except ImportError:
        from . import ml_stub as ml
        USING_STUB = True
else:
    from . import ml_stub as ml
    USING_STUB = True
