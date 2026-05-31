from pydantic import BaseModel, Field


class ApiKeyStatus(BaseModel):
    configured: bool
    key_preview: str | None = None


class ApiKeyListResponse(BaseModel):
    deepseek: ApiKeyStatus
    qwen: ApiKeyStatus
    tavily: ApiKeyStatus


class ApiKeyUpdateRequest(BaseModel):
    deepseek_api_key: str | None = Field(default=None)
    deepseek_base_url: str | None = Field(default=None)
    qwen_api_key: str | None = Field(default=None)
    qwen_base_url: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)


class TestConnectionResponse(BaseModel):
    connected: bool
    error: str | None = None


class TokenStatusResponse(BaseModel):
    has_personal_keys: bool
    free_tokens_remaining: int
    free_tokens_total: int
    free_tokens_used: int


class ProviderInfo(BaseModel):
    provider: str
    name: str
    description: str
    website: str
    price: str
    api_key_url: str
