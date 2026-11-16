"""Schema API cấu hình server Discord: kênh bật bằng `/setup` và xóa ký ức bằng `/clear`.

Chỉ bot (service token) gọi. ID Discord là snowflake dạng chuỗi số, tối đa 32 ký tự như `guild_id` của ChatRequest.
`user_hash` là SHA-256 hex (không muối) của Discord user id do bot tự băm, cùng công thức với `external_ref` của /ask:
backend không nhận ID thô, nhưng đây chỉ là bút danh (pseudonym), không ẩn danh: Discord ID là số công khai nên ai có
danh sách ID thành viên đều băm lại được để đối chiếu. Cải thiện (HMAC với khóa bí mật chung bot-backend) cần sửa bot
đồng bộ.

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
    user_hash: UserHash = Field(description="SHA-256 hex của Discord user id (bot băm; bút danh, không phải ẩn danh).")


class ClearAllMemory(BaseModel):
    scope: Literal["all"]


ClearMemoryRequest = Annotated[ClearUserMemory | ClearAllMemory, Field(discriminator="scope")]


class ClearMemoryResult(BaseModel):
    guild_id: str
    scope: Literal["user", "all"]
    conversations: int = Field(
        description="Số hội thoại đã xóa; tin nhắn, đánh giá và ký ức của chúng xóa theo (cascade), không đếm riêng."
    )
    threads_kept: int = Field(
        description="Số hội thoại thread của server được giữ nguyên khi scope=user (thread dùng chung, chỉ `all` xóa); "
        "luôn 0 khi scope=all."
    )
    vector_conversations: int = Field(
        description="Số hội thoại đã xóa điểm ký ức ở Qdrant (không phải số điểm); 0 nếu không có kho vector."
    )
