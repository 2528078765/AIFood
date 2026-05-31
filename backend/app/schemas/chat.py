from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    image: str | None = Field(default=None, description="base64 (降级路径)")
    image_url: str | None = Field(default=None, description="OSS URL (推荐)")


class ChatResponse(BaseModel):
    reply: str


class ChatHistoryItem(BaseModel):
    role: str  # "user" | "assistant"
    message: str
    created_at: str
