"""FeedbackRequest: 👍/👎 cho một câu trả lời.

Phụ trách: TV1 · [S2] API contract v1
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    message_id: UUID
    rating: Literal[1, -1]
    reason: Annotated[str, Field(max_length=500)] | None = None
