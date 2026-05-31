"""LangChain agent for AIFood fitness nutrition assistant.

Uses ChatDeepSeek as the reasoning LLM, coordinates 6 custom tools,
and maintains per-user conversation memory via Redis.

Exports
-------
AgentEvent : dataclass
    Streaming event emitted during agent execution.
run_agent : async generator
    Core function that runs the agent and yields AgentEvent instances.
get_chat_history : async function
    Read conversation history from Redis for a given user.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import AsyncIterator

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_deepseek import ChatDeepSeek

from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from app.services.api_key_service import get_user_llm_config

logger = logging.getLogger(__name__)

# In-memory chat history (replaces Redis for lightweight deployment)
_chat_history_store: dict[str, list[dict]] = defaultdict(list)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class AgentEvent:
    """Single streaming event emitted during agent execution.

    Attributes
    ----------
    event_type : str
        One of ``"thinking"``, ``"tool_call"``, ``"tool_result"``, ``"final"``.
    data : dict
        Payload whose shape depends on *event_type*:
        - thinking  → ``{"text": str}``
        - tool_call → ``{"tool": str, "input": str}``
        - tool_result → ``{"tool": str, "output": str}``
        - final → ``{"reply": str}``
    """

    event_type: str
    data: dict


# ---------------------------------------------------------------------------
# Safe tool imports
# ---------------------------------------------------------------------------

def _load_tools():
    """Import all 6 agent tools, gracefully skipping ones that do not exist yet.

    Returns
    -------
    list
        LangChain Tool / StructuredTool instances that were successfully loaded.
    """
    tools = []
    errors: list[str] = []

    # 1. Food recognition (Qwen-VL based)
    try:
        from app.agent.tools.food_recognition import recognize_food

        tools.append(recognize_food)
    except ImportError as e:
        errors.append(f"food_recognition: {e}")

    # 2. Nutrition search
    try:
        from app.agent.tools.nutrition_search import search_nutrition

        tools.append(search_nutrition)
    except ImportError as e:
        errors.append(f"nutrition_search: {e}")

    # 3. Recipe recommendation
    try:
        from app.agent.tools.recipe_recommend import recommend_recipe

        tools.append(recommend_recipe)
    except ImportError as e:
        errors.append(f"recipe_recommend: {e}")

    # 4. Fitness check-in
    try:
        from app.agent.tools.fitness_checkin import log_fitness

        tools.append(log_fitness)
    except ImportError as e:
        errors.append(f"fitness_checkin: {e}")

    # 5. Dashboard
    try:
        from app.agent.tools.dashboard import get_dashboard

        tools.append(get_dashboard)
    except ImportError as e:
        errors.append(f"dashboard: {e}")

    # 6. Web search (Tavily)
    try:
        from app.agent.tools.web_search import search_web

        tools.append(search_web)
    except ImportError as e:
        errors.append(f"web_search: {e}")

    if errors:
        logger.warning(
            "Some agent tools could not be loaded (%d/6 loaded):\n  %s",
            len(tools),
            "\n  ".join(errors),
        )

    return tools


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------


async def get_chat_history(user_id: str, limit: int = 20) -> list[dict]:
    """Read the most recent chat messages for *user_id* from in-memory store."""
    messages = _chat_history_store.get(user_id, [])
    return messages[-limit:] if messages else []


async def save_chat_message(user_id: str, role: str, message: str) -> None:
    """Save a chat message to the in-memory store."""
    from datetime import datetime
    _chat_history_store[user_id].append({
        "role": role,
        "message": message,
        "created_at": datetime.utcnow().isoformat(),
    })


# ---------------------------------------------------------------------------
# Core agent runner
# ---------------------------------------------------------------------------


async def run_agent(
    user_id: str,
    message: str,
    image_url: str | None = None,
    db=None,
) -> AsyncIterator[AgentEvent]:
    """Execute the fitness nutrition agent and stream events.

    Parameters
    ----------
    user_id : str
        UUID of the current user.
    message : str
        User's natural-language message.
    image_url : str or None
        Optional OSS URL of a food photo to recognise.
    db : AsyncSession or None
        SQLAlchemy async session for resolving per-user LLM credentials.

    Yields
    ------
    AgentEvent
        A sequence of ``thinking``, ``tool_call``, ``tool_result``, and
        ``final`` events.
    """
    # ------------------------------------------------------------------
    # 1. Load per-user LLM configuration
    # ------------------------------------------------------------------
    llm_config = await get_user_llm_config(str(user_id), db)

    if not llm_config.deepseek_api_key:
        yield AgentEvent(
            event_type="final",
            data={
                "reply": (
                    "您的免费 100 万 Token 已用完，请前往「我的」→「API 密钥设置」页面配置您自己的 API 密钥。\n\n"
                    "推荐使用 DeepSeek（性价比最高，￥2/百万token），申请地址：https://platform.deepseek.com"
                )
            },
        )
        return

    # ------------------------------------------------------------------
    # 1.5. Fetch user profile for personalised system prompt
    # ------------------------------------------------------------------
    import uuid as _uuid
    from sqlalchemy import select
    from app.models.user import User
    user_result = await db.execute(select(User).where(User.id == _uuid.UUID(user_id)))
    user = user_result.scalar_one_or_none()
    dynamic_prompt = _build_dynamic_prompt(user)

    # ------------------------------------------------------------------
    # 2. Build LLM instance
    # ------------------------------------------------------------------
    llm = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.3,
        max_tokens=2048,
        api_key=llm_config.deepseek_api_key,
        api_base=llm_config.deepseek_base_url,
    )

    # ------------------------------------------------------------------
    # 3. Set per-request context (user_id, db) for tools
    # ------------------------------------------------------------------
    from app.agent.context import set_agent_context
    set_agent_context(str(user_id), db)

    # ------------------------------------------------------------------
    # 4. Load tools
    # ------------------------------------------------------------------
    tools = _load_tools()

    # ------------------------------------------------------------------
    # 4. Memory — in-process window (Redis optional)
    # ------------------------------------------------------------------
    memory = ConversationBufferWindowMemory(
        k=10,
        memory_key="chat_history",
        return_messages=True,
    )

    # ------------------------------------------------------------------
    # 5. Prompt template
    # ------------------------------------------------------------------
    prompt = ChatPromptTemplate.from_messages([
        ("system", dynamic_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # ------------------------------------------------------------------
    # 6. Build agent + executor
    # ------------------------------------------------------------------
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=settings.debug,
        handle_parsing_errors=True,
        max_iterations=5,
    )

    # ------------------------------------------------------------------
    # 7. Prepare input — prepend image URL if provided
    # ------------------------------------------------------------------
    if image_url:
        full_message = (
            f"[用户上传了一张食物图片，图片链接: {image_url}]\n\n{message}"
        )
    else:
        full_message = message

    # ------------------------------------------------------------------
    # 8. Stream via astream_events (v2)
    # ------------------------------------------------------------------
    final_output: str = ""

    try:
        async for event in agent_executor.astream_events(
            {"input": full_message},
            version="v2",
        ):
            kind = event.get("event", "")

            # ── LLM streaming tokens → "thinking" ──
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk is not None and hasattr(chunk, "content"):
                    content = chunk.content
                    if isinstance(content, str) and content.strip():
                        yield AgentEvent(
                            event_type="thinking",
                            data={"text": content},
                        )

            # ── Tool invocation starting → "tool_call" ──
            elif kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                yield AgentEvent(
                    event_type="tool_call",
                    data={
                        "tool": tool_name,
                        "input": _safe_serialize(tool_input),
                    },
                )

            # ── Tool returned → "tool_result" ──
            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                output = event.get("data", {}).get("output", "")
                yield AgentEvent(
                    event_type="tool_result",
                    data={
                        "tool": tool_name,
                        "output": _safe_serialize(output)[:1000],
                    },
                )

            # ── AgentExecutor finished → capture final output ──
            elif kind == "on_chain_end" and event.get("name") == "AgentExecutor":
                raw = event.get("data", {}).get("output", "")
                final_output = _extract_reply(raw)

    except Exception as exc:
        logger.exception("Agent execution failed for user %s", user_id)
        final_output = (
            f"抱歉，处理您的请求时遇到了问题，请稍后再试。"
        )
        yield AgentEvent(
            event_type="thinking",
            data={"text": f"内部错误：{exc}"},
        )

    # ------------------------------------------------------------------
    # 9. Yield the final answer
    # ------------------------------------------------------------------
    if not final_output:
        final_output = "抱歉，我暂时无法回答您的问题，请换个方式描述一下？"

    estimated_tokens = max(1, (len(full_message) + len(final_output)) // 2)

    yield AgentEvent(
        event_type="final",
        data={
            "reply": final_output,
            "tokens_used": estimated_tokens,
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_serialize(obj) -> str:
    """Convert any object to a human-readable string, safely."""
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError, OverflowError):
        return str(obj)[:2000]


def _build_dynamic_prompt(user) -> str:
    """Build a personalised system prompt with the user's body data."""
    if not user:
        return SYSTEM_PROMPT

    from datetime import date
    from app.services.body_fat import estimate_body_fat

    goal_map = {"lose_fat": "减脂", "build_muscle": "增肌", "maintain": "维持健康"}
    goal_label = goal_map.get(user.fitness_goal, "未设置")
    gender_label = "男" if user.gender == "male" else "女" if user.gender == "female" else "未设置"

    # Calculate age
    age = "未知"
    if user.birthday:
        today = date.today()
        age = str(today.year - user.birthday.year - ((today.month, today.day) < (user.birthday.month, user.birthday.day)))

    # Estimate body fat
    bf_info = estimate_body_fat(
        height_cm=user.height_cm, weight_kg=user.weight_kg,
        gender=user.gender, birthday=user.birthday,
        exercise_details=user.exercise_details,
    )

    profile_lines = [
        f"- 性别：{gender_label}，年龄：{age}岁",
        f"- 身高：{user.height_cm or '未设置'}cm，体重：{user.weight_kg or '未设置'}kg",
        f"- 健身目标：{goal_label}，每日热量目标：{user.daily_calorie_target or '未计算'}kcal",
    ]
    if bf_info.get("body_fat_pct"):
        profile_lines.append(
            f"- 估算体脂率：{bf_info['body_fat_pct']}%（BMI {bf_info['bmi']}，FFMI {bf_info['ffmi']}，力量水平：{bf_info.get('strength_level', 'unknown')}）")
    if user.exercise_details:
        profile_lines.append(f"- 运动详情：{user.exercise_details}")
    if user.allergies:
        profile_lines.append(f"- 过敏原：{', '.join(user.allergies)}")
    if user.dietary_restrictions:
        profile_lines.append(f"- 饮食限制：{', '.join(user.dietary_restrictions)}")

    user_section = "\n".join(profile_lines)

    return SYSTEM_PROMPT + f"\n\n## 当前用户身体数据\n{user_section}\n\n请在回答中结合以上用户数据给出个性化建议。"


def _extract_reply(output) -> str:
    """Pull the final reply string from an AgentExecutor return value."""
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        # AgentExecutor commonly wraps the answer in {"output": "..."}
        return str(output.get("output", output))
    return str(output) if output else ""
