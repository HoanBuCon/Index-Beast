"""Schema cho GET /health.

Phụ trách: TV1 · [S1] Skeleton FastAPI
"""

from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, bool]
