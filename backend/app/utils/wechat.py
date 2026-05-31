import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def code2session(code: str) -> dict:
    """Exchange WeChat login code for openid and session_key.

    Retries up to 2 times on connection errors (the WeChat API
    occasionally returns 408 / ConnectTimeout from Cloud Run).
    """
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    last_error = None

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(f"code2session attempt {attempt+1}: HTTP {resp.status_code}")
                    last_error = Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    if attempt < 2:
                        await asyncio.sleep(1)
                        continue
                    raise last_error
                data = resp.json()
                if "errcode" in data and data["errcode"] != 0:
                    raise ValueError(f"WeChat API error: {data.get('errmsg', 'unknown')}")
                return data
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
            logger.warning(f"code2session attempt {attempt+1} failed: {e}")
            last_error = e
            if attempt < 2:
                await asyncio.sleep(1)
        except Exception:
            logger.exception("code2session failed")
            raise

    raise last_error or Exception("code2session failed after 3 attempts")
