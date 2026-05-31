"""
Web search tool: call Tavily Search API for real-time web information.

Loads the Tavily API key from user config (with fallback to .env).
"""
import json as json_lib
from typing import Optional

from langchain.tools import tool


from app.database import async_session
from app.services.api_key_service import get_user_llm_config

# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
async def search_web(query: str) -> str:
    """使用 Tavily Search API 进行实时网络搜索，获取最新信息。

    参数:
    - query: 搜索关键词（必填）

    返回: JSON 格式的搜索结果列表（最多3条），每条包含 title/url/content，或错误信息。

    使用场景:
    - 需要获取模型训练数据之外的实时信息时调用
    - 搜索健身食谱、营养知识、最新健康资讯等
    """
    from app.agent.context import get_agent_context
    ctx = get_agent_context()
    user_id = ctx.get("user_id", "")
    db = ctx.get("db")
    session = db if db is not None else async_session()
    close_session = db is None

    try:
        # Load Tavily API key from user config
        llm_config = await get_user_llm_config(user_id, session)

        if not llm_config.tavily_api_key:
            return (
                "[错误] 未配置 Tavily API Key。请在设置页面配置您的 Tavily API Key，"
                "或联系管理员。Tavily 官网: https://tavily.com"
            )

        # Import tavily lazily to avoid import errors if not installed
        try:
            from tavily import TavilyClient
        except ImportError:
            return (
                "[错误] tavily-python 包未安装。"
                "请运行: pip install tavily-python"
            )

        try:
            client = TavilyClient(api_key=llm_config.tavily_api_key)
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=3,
            )
        except Exception as api_err:
            error_msg = str(api_err)
            return (
                f"[错误] Tavily 搜索 API 调用失败: {error_msg}"
            )

        # Extract and format results
        results = response.get("results", [])
        if not results:
            return f"[提示] 搜索 '{query}' 未返回任何结果。"

        formatted = []
        for r in results[:3]:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],  # Truncate long content
            })

        return json_lib.dumps(formatted, ensure_ascii=False, indent=2)

    except Exception as exc:
        return f"[错误] 网络搜索异常: {exc}"
    finally:
        if close_session:
            await session.close()
