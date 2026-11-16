"""Schema API cấu hình server Discord: kênh bật bằng `/setup` và xóa ký ức bằng `/clear`.

Chỉ bot (service token) gọi. ID Discord là snowflake dạng chuỗi số, tối đa 32 ký tự như `guild_id` của ChatRequest.
`user_hash` là SHA-256 hex của Discord user id do bot tự băm (cùng công thức với `external_ref` của /ask),
nên backend không bao giờ nhận ID người dùng thô (NFR-PRIV-01).

Phụ trách: TV1 · [S5] API server Discord cho bot
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

MAX_CHANNELS_PER_GUILD = 50

UserHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class GuildChannelOut(BaseModel):
    channel_id: str
    enabled_at: datetime


class GuildChannelsOut(BaseModel):
    guild_id: str
    channels: list[GuildChannelOut]
    limit: int = Field(MAX_CHANNELS_PER_GUILD, description="Số kênh tối đa mỗi server.")


class ChannelsRemoved(BaseModel):
    deleted: int = Field(description="Số kênh vừa tắt; 0 khi kênh chưa bật (gọi lại vẫn 200).")


class ClearUserMemory(BaseModel):
    scope: Literal["user"]
    user_hash: UserHash = Field(description="SHA-256 hex của Discord user id (bot băm, không gửi ID thô).")


class ClearAllMemory(BaseModel):
    scope: Literal["all"]


ClearMemoryRequest = Annotated[ClearUserMemory | ClearAllMemory, Field(discriminator="scope")]


class ClearMemoryResult(BaseModel):
    guild_id: str
    scope: Literal["user", "all"]
    conversations: int
    messages: int
    feedback: int
    memories: int = Field(description="Dòng ký ức dài hạn trong PostgreSQL.")
    vector_points: int = Field(description="Điểm ký ức ngữ nghĩa trong Qdrant; 0 khi không có kho vector.")
