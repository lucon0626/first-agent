"""
LLM 调用模块 — 封装与大语言模型的所有通信。

职责：
1. 管理 OpenAI 客户端实例（懒加载，避免重复创建）
2. 发送消息并获取回复
3. 自动重试网络超时和限流错误（指数退避）
4. 记录每次调用的日志（模型、token 用量等）
"""
import os
import time
from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError, AuthenticationError
from config import get_model, get_base_url, get_llm_timeout, get_llm_max_retries
import logger

# 全局客户端实例（懒加载，第一次调用时创建）
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """
    获取或创建 OpenAI 客户端。
    使用懒加载模式：只在第一次调用时创建，之后复用同一实例。
    """
    global _client
    if _client is None:
        kwargs: dict = {"api_key": os.environ["OPENAI_API_KEY"]}
        # 如果配置了自定义 API 地址（如 DeepSeek），则设置 base_url
        base_url = get_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        _client = OpenAI(**kwargs)
    return _client


def chat(messages: list[dict]) -> str:
    """
    发送消息列表给 LLM，返回回复文字。

    自动处理：
    - 网络超时 → 指数退避重试（1s → 2s → 4s）
    - 429 限流 → 同上
    - 401 认证失败 → 直接抛出，不重试
    - 其他异常 → 返回错误信息字符串

    参数:
        messages: OpenAI 格式的消息列表，如 [{"role": "user", "content": "你好"}]

    返回:
        LLM 的回复文字，或以 "LLM 调用失败" 开头的错误信息
    """
    model = get_model()
    timeout = get_llm_timeout()
    max_retries = get_llm_max_retries()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = _get_client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,   # 设为 0 让输出更确定
                timeout=timeout,  # 单次请求超时
            )
            if not response.choices:
                logger.error("LLM 返回空 choices")
                return "LLM 调用失败：模型未返回任何内容"
            content = response.choices[0].message.content

            # 记录 token 用量（如果 API 返回了的话）
            tokens = getattr(response, "usage", None)
            total_tokens = tokens.total_tokens if tokens else None
            logger.log_llm_call(model, len(messages), content, total_tokens)
            return content

        except AuthenticationError as e:
            # 认证失败说明 Key 有问题，重试没意义，直接报错
            logger.error(f"API 认证失败: {e}")
            raise

        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            # 这三类错误是暂时性的，值得重试
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt  # 退避时间：1s, 2s, 4s
                logger.warning(f"LLM 调用失败（{type(e).__name__}），{wait}s 后重试 ({attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                logger.error(f"LLM 调用失败，已重试 {max_retries} 次: {e}")

        except Exception as e:
            # 其他未知异常，不重试
            logger.error(f"LLM 调用异常: {e}")
            return f"LLM 调用失败: {e}"

    # 所有重试都失败了
    return f"LLM 调用失败（已重试 {max_retries} 次）: {last_error}"
