"""Chat API endpoints — streaming SSE, non-streaming, and history."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.agent import AgentEvent, get_chat_history, run_agent, save_chat_message
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.schemas.common import APIResponse
from app.services.api_key_service import deduct_tokens
from app.utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{settings.api_prefix}/chat",
    tags=["chat"],
)


# ======================================================================
# POST /api/chat/stream  —  SSE streaming (primary path)
# ======================================================================


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream agent events as Server-Sent Events.

    Each ``AgentEvent`` is converted to an SSE frame::

        event: {event_type}
        data: {json}

    The final event always carries ``event_type="final"`` with the
    complete agent reply in ``data.reply``.
    """

    async def event_stream():
        tokens_used = 0
        final_reply = ""
        try:
            async for ev in run_agent(
                user_id=str(user.id),
                message=req.message,
                image_url=req.image_url,
                db=db,
            ):
                if ev.event_type == "final":
                    tokens_used = ev.data.get("tokens_used", 0)
                    final_reply = ev.data.get("reply", "")
                yield _event_to_sse(ev)
        except Exception as exc:
            logger.exception("SSE stream error for user %s", user.id)
            final_reply = "系统繁忙，请稍后再试。"
            yield _event_to_sse(
                AgentEvent(
                    event_type="final",
                    data={"reply": final_reply},
                )
            )
        if tokens_used > 0:
            try:
                await deduct_tokens(str(user.id), tokens_used, db)
            except Exception:
                logger.exception("Failed to deduct tokens for user %s", user.id)
        await save_chat_message(str(user.id), "user", req.message)
        if final_reply:
            await save_chat_message(str(user.id), "assistant", final_reply)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ======================================================================
# POST /api/chat  —  non-streaming (fallback / simpler client path)
# ======================================================================


@router.post("", response_model=APIResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Non-streaming chat.  Collects all agent events and returns the
    final reply as a plain JSON response."""
    final_reply = ""
    tokens_used = 0
    try:
        async for ev in run_agent(
            user_id=str(user.id),
            message=req.message,
            image_url=req.image_url,
            db=db,
        ):
            if ev.event_type == "final":
                final_reply = ev.data.get("reply", final_reply)
                tokens_used = ev.data.get("tokens_used", 0)
    except Exception as exc:
        logger.exception("Chat error for user %s", user.id)
        return APIResponse.error(
            code=500,
            message="处理对话时发生错误，请稍后再试",
        )

    if tokens_used > 0:
        try:
            await deduct_tokens(str(user.id), tokens_used, db)
        except Exception:
            logger.exception("Failed to deduct tokens for user %s", user.id)

    if not final_reply:
        final_reply = "抱歉，我暂时无法回答您的问题，请换个方式描述一下？"

    await save_chat_message(str(user.id), "user", req.message)
    await save_chat_message(str(user.id), "assistant", final_reply)

    return APIResponse.success(data={"reply": final_reply})


# ======================================================================
# GET /api/chat/history  — conversation history from Redis
# ======================================================================


@router.get("/history", response_model=APIResponse)
async def chat_history(
    limit: int = 20,
    user: User = Depends(get_current_user),
):
    """Return the most recent *limit* chat messages for the current user.

    Messages are read from the same Redis list that backs the agent's
    ``ConversationBufferWindowMemory``.
    """
    try:
        history = await get_chat_history(
            user_id=str(user.id),
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Failed to read chat history for user %s", user.id)
        return APIResponse.error(
            code=500,
            message="读取对话历史失败",
        )

    return APIResponse.success(data=history)


# ======================================================================
# Helpers
# ======================================================================


def _event_to_sse(ev: AgentEvent) -> str:
    """Convert an ``AgentEvent`` into an SSE frame string."""
    payload = json.dumps(ev.data, ensure_ascii=False, default=str)
    return f"event: {ev.event_type}\ndata: {payload}\n\n"
