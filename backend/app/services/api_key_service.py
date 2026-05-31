"""用户 LLM 配置动态加载——1000W 免费 Token 制，用完后需自配密钥."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.utils.crypto import decrypt_api_key

FREE_TOKEN_TOTAL = 1_000_000


@dataclass
class LLMConfig:
    deepseek_api_key: str
    deepseek_base_url: str
    qwen_api_key: str
    qwen_base_url: str
    tavily_api_key: str


@dataclass
class TokenStatus:
    has_personal_keys: bool
    free_tokens_remaining: int
    free_tokens_total: int
    free_tokens_used: int


async def get_token_status(user_id: str, db: AsyncSession) -> TokenStatus:
    """获取用户 Token 余额和密钥配置状态."""
    uid = uuid.UUID(user_id)
    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    remaining = user.free_tokens_remaining if user else 0
    if remaining is None:
        remaining = 0

    has_personal = await _has_personal_keys(user_id, db)

    return TokenStatus(
        has_personal_keys=has_personal,
        free_tokens_remaining=remaining,
        free_tokens_total=FREE_TOKEN_TOTAL,
        free_tokens_used=FREE_TOKEN_TOTAL - remaining,
    )


async def deduct_tokens(user_id: str, amount: int, db: AsyncSession) -> int:
    """扣减免费 Token，返回剩余数量。如果用户有自有密钥则不扣减."""
    uid = uuid.UUID(user_id)
    has_personal = await _has_personal_keys(user_id, db)
    if has_personal:
        # User has own keys, don't deduct free tokens
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        return user.free_tokens_remaining if user else 0

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user:
        return 0

    remaining = user.free_tokens_remaining or 0
    user.free_tokens_remaining = max(0, remaining - amount)
    await db.commit()
    await db.refresh(user)
    return user.free_tokens_remaining


async def _has_personal_keys(user_id: str, db: AsyncSession) -> bool:
    """检查用户是否配置了至少一个自有 API key."""
    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == uid)
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    return bool(row.deepseek_api_key or row.qwen_api_key or row.tavily_api_key)


async def get_user_llm_config(user_id: str, db: AsyncSession) -> LLMConfig:
    """优先用户自配密钥，其次检查免费 Token 余额，都没有返回空密钥."""
    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == uid, UserApiKey.is_active == True)
    )
    row = result.scalar_one_or_none()

    if row and row.deepseek_api_key:
        return LLMConfig(
            deepseek_api_key=decrypt_api_key(row.deepseek_api_key),
            deepseek_base_url=row.deepseek_base_url or "https://api.deepseek.com",
            qwen_api_key=decrypt_api_key(row.qwen_api_key or ""),
            qwen_base_url=row.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            tavily_api_key=decrypt_api_key(row.tavily_api_key or ""),
        )

    # Check free tokens
    user_result = await db.execute(select(User).where(User.id == uid))
    user = user_result.scalar_one_or_none()
    remaining = (user and user.free_tokens_remaining) or 0

    if remaining > 0:
        return LLMConfig(
            deepseek_api_key=settings.deepseek_api_key,
            deepseek_base_url=settings.deepseek_base_url,
            qwen_api_key=settings.dashscope_api_key,
            qwen_base_url=settings.dashscope_base_url,
            tavily_api_key=settings.tavily_api_key,
        )

    # No free tokens and no personal keys
    return LLMConfig(
        deepseek_api_key="",
        deepseek_base_url="https://api.deepseek.com",
        qwen_api_key="",
        qwen_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        tavily_api_key="",
    )
