from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.database import get_db
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.schemas.common import APIResponse
from app.schemas.settings import (
    ApiKeyStatus,
    ApiKeyUpdateRequest,
    ProviderInfo,
    TokenStatusResponse,
)
from app.services.api_key_service import get_token_status, FREE_TOKEN_TOTAL
from app.utils.crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.utils.security import get_current_user

router = APIRouter(prefix=f"{app_settings.api_prefix}/settings", tags=["settings"])

VALID_PROVIDERS = {"deepseek", "qwen", "tavily"}

PROVIDER_LIST = [
    ProviderInfo(
        provider="deepseek",
        name="DeepSeek",
        description="国产高性价比 AI 模型，V3 推理能力出色",
        website="https://platform.deepseek.com",
        price="￥2 / 百万 token",
        api_key_url="https://platform.deepseek.com/api_keys",
    ),
    ProviderInfo(
        provider="qwen",
        name="通义千问 (Qwen)",
        description="阿里云视觉识别，用于食物拍照分析",
        website="https://dashscope.aliyun.com",
        price="视觉模型 ￥0.002 / 次",
        api_key_url="https://dashscope.console.aliyun.com/apiKey",
    ),
    ProviderInfo(
        provider="tavily",
        name="Tavily Search",
        description="AI 联网搜索引擎，获取最新资讯",
        website="https://tavily.com",
        price="免费额度 1000 次/月",
        api_key_url="https://app.tavily.com/home",
    ),
]


def _build_status(row: UserApiKey | None) -> dict[str, ApiKeyStatus]:
    return {
        "deepseek": ApiKeyStatus(
            configured=bool(row and row.deepseek_api_key),
            key_preview=mask_api_key(decrypt_api_key(row.deepseek_api_key))
            if row and row.deepseek_api_key
            else None,
        ),
        "qwen": ApiKeyStatus(
            configured=bool(row and row.qwen_api_key),
            key_preview=mask_api_key(decrypt_api_key(row.qwen_api_key))
            if row and row.qwen_api_key
            else None,
        ),
        "tavily": ApiKeyStatus(
            configured=bool(row and row.tavily_api_key),
            key_preview=mask_api_key(decrypt_api_key(row.tavily_api_key))
            if row and row.tavily_api_key
            else None,
        ),
    }


@router.get("/token-status", response_model=APIResponse)
async def token_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取免费 Token 余额和配置状态."""
    status = await get_token_status(str(user.id), db)
    return APIResponse.success(data=TokenStatusResponse(
        has_personal_keys=status.has_personal_keys,
        free_tokens_remaining=status.free_tokens_remaining,
        free_tokens_total=status.free_tokens_total,
        free_tokens_used=status.free_tokens_used,
    ).model_dump())


@router.get("/providers", response_model=APIResponse)
async def list_providers():
    """获取支持的 AI 提供商列表及申请教程."""
    return APIResponse.success(data=[p.model_dump() for p in PROVIDER_LIST])


@router.get("/apikeys", response_model=APIResponse)
async def get_api_keys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户 API Key 状态（脱敏）+ Token 余额."""
    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()
    keys = _build_status(row)
    token = await get_token_status(str(user.id), db)
    return APIResponse.success(data={
        "keys": keys,
        "token": TokenStatusResponse(
            has_personal_keys=token.has_personal_keys,
            free_tokens_remaining=token.free_tokens_remaining,
            free_tokens_total=token.free_tokens_total,
            free_tokens_used=token.free_tokens_used,
        ).model_dump(),
        "providers": [p.model_dump() for p in PROVIDER_LIST],
    })


@router.put("/apikeys", response_model=APIResponse)
async def update_api_keys(
    payload: ApiKeyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """保存/更新 API Key（加密存储）."""
    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = UserApiKey(user_id=user.id)
        db.add(row)

    update_map = {
        "deepseek_api_key": payload.deepseek_api_key,
        "deepseek_base_url": payload.deepseek_base_url,
        "qwen_api_key": payload.qwen_api_key,
        "qwen_base_url": payload.qwen_base_url,
        "tavily_api_key": payload.tavily_api_key,
    }

    for field, value in update_map.items():
        if value is not None:
            if field.endswith("_api_key"):
                setattr(row, field, encrypt_api_key(value) if value else None)
            else:
                setattr(row, field, value)

    await db.commit()
    await db.refresh(row)

    return APIResponse.success(data=_build_status(row))


@router.delete("/apikeys", response_model=APIResponse)
async def delete_api_key(
    provider: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除某个 API Key."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Invalid provider: {provider}")

    result = await db.execute(
        select(UserApiKey).where(UserApiKey.user_id == user.id)
    )
    row = result.scalar_one_or_none()

    if row:
        key_field = f"{provider}_api_key"
        setattr(row, key_field, None)
        await db.commit()

    return APIResponse.success(data={"deleted": provider})


@router.post("/test-connection", response_model=APIResponse)
async def test_connection(
    provider: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """测试 API Key 连接是否有效."""
    if provider not in VALID_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Invalid provider: {provider}")

    from app.services.api_key_service import get_user_llm_config

    config = await get_user_llm_config(str(user.id), db)

    if provider == "deepseek":
        api_key = config.deepseek_api_key
    elif provider == "qwen":
        api_key = config.qwen_api_key
    else:
        api_key = config.tavily_api_key

    if not api_key:
        return APIResponse.success(
            data={"connected": False, "error": "未配置 API Key，请先配置或免费 Token 已用完"}
        )

    return APIResponse.success(data={"connected": True, "error": None})
