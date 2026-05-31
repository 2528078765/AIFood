"""
Food recognition tool: download image from OSS, call Qwen-VL, parse and store results.

Uses DashScope-compatible OpenAI endpoint to invoke Qwen-VL for food identification.
"""
import base64
import json as json_lib
import uuid
from datetime import date
from typing import Optional

import httpx
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError


from app.database import async_session
from app.models.food_record import FoodRecord
from app.services.api_key_service import get_user_llm_config


# ---------------------------------------------------------------------------
# Pydantic schema for validating a single food item from the VL model response
# ---------------------------------------------------------------------------

class RecognizedFoodItem(BaseModel):
    name: str
    estimated_weight_g: Optional[float] = None
    estimated_calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None


SYSTEM_PROMPT = (
    "你是一个专业营养师。识别图片中所有食物，只返回 JSON 数组。"
    "每个食物包含: name(名称), estimated_weight_g(估算克数), estimated_calories(估算热量), "
    "protein_g(蛋白质), fat_g(脂肪), carbs_g(碳水)。不要额外文字。"
)

RETRY_PROMPT = (
    "你是一个专业营养师。请严格只输出一个 JSON 数组，不要包含任何解释、Markdown 标记或额外文字。"
    "数组中每个元素是一个 JSON 对象，必须包含以下字段: "
    "name(食物名称,字符串), estimated_weight_g(估算克数,数字), "
    "estimated_calories(估算热量,数字), protein_g(蛋白质克数,数字), "
    "fat_g(脂肪克数,数字), carbs_g(碳水克数,数字)。"
    "示例格式: [{\"name\":\"米饭\",\"estimated_weight_g\":200,\"estimated_calories\":232,"
    "\"protein_g\":5.2,\"fat_g\":0.6,\"carbs_g\":51.8}]"
    "\n\n请识别图片中的所有食物并输出 JSON 数组。"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _download_image_as_base64(image_url: str) -> str:
    """Download an image from *image_url* and return its base64 data-URI string."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        b64 = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{content_type};base64,{b64}"


def _extract_json(text: str) -> str:
    """Best-effort extraction of a JSON array from model output that may contain
    markdown fences or surrounding prose."""
    text = text.strip()
    # Strip ```json / ``` fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening fence
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Try to find the first '[' and last ']'
    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        return text[arr_start : arr_end + 1]
    return text


def _build_food_record(
    user_id: str,
    image_url: str,
    foods: list[dict],
) -> FoodRecord:
    """Build a FoodRecord ORM instance from the parsed food list."""
    total_calories = 0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0

    for f in foods:
        total_calories += int(f.get("estimated_calories") or 0)
        total_protein += float(f.get("protein_g") or 0)
        total_fat += float(f.get("fat_g") or 0)
        total_carbs += float(f.get("carbs_g") or 0)

    return FoodRecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        image_url=image_url,
        foods=foods,
        total_calories=total_calories,
        total_protein_g=round(total_protein, 1) if total_protein else None,
        total_fat_g=round(total_fat, 1) if total_fat else None,
        total_carbs_g=round(total_carbs, 1) if total_carbs else None,
        recorded_at=date.today(),
    )


async def _call_qwen_vl(
    image_data_uri: str,
    llm_config,
    prompt: str,
) -> str:
    """Call Qwen-VL via DashScope-compatible endpoint and return the text response."""
    llm = ChatOpenAI(
        model="qwen-vl-max",
        base_url=llm_config.qwen_base_url,
        api_key=llm_config.qwen_api_key,
        temperature=0.1,
        max_tokens=2048,
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ],
        }
    ]
    response = await llm.ainvoke(messages)
    return response.content if hasattr(response, "content") else str(response)


async def _parse_and_validate(raw_text: str) -> list[dict]:
    """Parse model text → list of validated dicts.  Raises on failure."""
    cleaned = _extract_json(raw_text)
    parsed = json_lib.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("Model output is not a JSON array")
    # Validate each item
    validated = [RecognizedFoodItem(**item).model_dump() for item in parsed]
    return validated


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------

@tool
async def recognize_food(image_url: str) -> str:
    """识别食物图片并返回食物列表和营养估算。传入图片 URL 即可。

    返回: JSON 格式的食物识别结果列表，或错误信息。
    该工具会下载图片、调用视觉模型识别食物、并将结果写入数据库。
    """
    from app.agent.context import get_agent_context
    ctx = get_agent_context()
    user_id = ctx.get("user_id", "")
    db = ctx.get("db")

    session = db if db is not None else async_session()
    close_session = db is None

    try:
        # 1. Load LLM config for this user
        llm_config = await get_user_llm_config(user_id, session)

        # 2. Download image
        try:
            image_data_uri = await _download_image_as_base64(image_url)
        except httpx.HTTPError as exc:
            return f"[错误] 无法下载图片: {exc}"
        except Exception as exc:
            return f"[错误] 图片处理失败: {exc}"

        # 3. Call Qwen-VL
        try:
            raw = await _call_qwen_vl(image_data_uri, llm_config, SYSTEM_PROMPT)
        except Exception as exc:
            return f"[错误] 视觉模型调用失败: {exc}"

        # 4. Parse & validate (with one retry on parse failure)
        foods: list[dict] = []
        try:
            foods = await _parse_and_validate(raw)
        except (json_lib.JSONDecodeError, ValueError, ValidationError) as e:
            # Retry with stronger prompt
            try:
                raw2 = await _call_qwen_vl(image_data_uri, llm_config, RETRY_PROMPT)
                foods = await _parse_and_validate(raw2)
            except Exception as retry_err:
                return (
                    f"[错误] 食物识别结果解析失败（已重试）。"
                    f"原始错误: {e}，重试错误: {retry_err}"
                )

        if not foods:
            return "[提示] 未能从图片中识别到任何食物，请确认图片包含清晰的食物内容。"

        # 5. Persist to database
        try:
            record = _build_food_record(user_id, image_url, foods)
            session.add(record)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            return f"[错误] 食物记录保存失败: {exc}"

        # 6. Return results
        return json_lib.dumps(foods, ensure_ascii=False, indent=2)

    except Exception as exc:
        if close_session:
            await session.rollback()
        return f"[错误] 食物识别过程异常: {exc}"
    finally:
        if close_session:
            await session.close()
