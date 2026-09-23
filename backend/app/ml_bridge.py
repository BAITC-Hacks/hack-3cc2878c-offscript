"""Use real ML by default; fixture data requires an explicit opt-in."""
from __future__ import annotations

from .settings import settings

if settings.use_ml_stub:
    from . import ml_stub as ml
    USING_STUB = True
else:
    from openwind_ml import api as ml
    USING_STUB = False
