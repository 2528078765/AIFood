import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, ProfileUpdate, UserProfile
from app.schemas.common import APIResponse
from app.services.calorie_service import calculate_user_daily_target
from app.utils.security import create_access_token, get_current_user
from app.utils.wechat import code2session

logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{settings.api_prefix}/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """WeChat code -> openid -> find/create user -> return JWT."""
    try:
        wx_data = await code2session(req.wechat_code)
        openid = wx_data["openid"]
    except Exception as e:
        logger.error(f"Login code2session failed: {e}")
        raise HTTPException(status_code=502, detail="WeChat authentication failed, please try again")

    result = await db.execute(select(User).where(User.wechat_openid == openid))
    user = result.scalar_one_or_none()

    if user is None:
        import time
        user = User(wechat_openid=openid)
        user.nickname = req.nickname or f"aifood_user_{int(time.time()) % 100000:05d}"
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif req.nickname and not user.nickname:
        user.nickname = req.nickname
        if req.avatar_url:
            user.avatar_url = req.avatar_url
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    return APIResponse.success(
        data={
            "access_token": token,
            "token_type": "bearer",
            "user": UserProfile.model_validate(user).model_dump(mode="json"),
        }
    )


@router.get("/profile", response_model=APIResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """获取当前用户完整信息."""
    return APIResponse.success(data=UserProfile.model_validate(user).model_dump(mode="json"))


@router.put("/profile", response_model=APIResponse)
async def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户身体数据，自动重算每日热量目标."""
    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user, key, value)

    # Recalculate calorie target if weight/goal changed
    if "weight_kg" in update_data or "fitness_goal" in update_data:
        if all([user.gender, user.weight_kg, user.height_cm, user.birthday, user.fitness_goal]):
            try:
                user.daily_calorie_target = calculate_user_daily_target(
                    gender=user.gender,
                    weight_kg=user.weight_kg,
                    height_cm=user.height_cm,
                    birthday=user.birthday,
                    goal=user.fitness_goal,
                )
            except ValueError:
                pass  # keep existing target if calc fails

    await db.commit()
    await db.refresh(user)

    # Calculate body fat on save if all required fields present
    from app.services.body_fat import estimate_body_fat
    data = UserProfile.model_validate(user).model_dump(mode="json")
    data["body_fat"] = estimate_body_fat(
        height_cm=user.height_cm,
        weight_kg=user.weight_kg,
        gender=user.gender,
        birthday=user.birthday,
        exercise_details=user.exercise_details,
    )
    return APIResponse.success(data=data)
