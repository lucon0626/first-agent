"""
配置中心 — 所有可调参数统一从环境变量读取，有合理默认值。
修改 .env 文件即可调整行为，无需改代码。
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def _env_int(key: str, default: int) -> int:
    """从环境变量读取整数，值非法时返回默认值。"""
    val = os.environ.get(key, "")
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def load_config() -> None:
    """
    启动时调用：加载 .env 文件到环境变量，检查必要配置。
    查找顺序：当前目录 → 上级目录（兼容从子目录运行的情况）。
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"

    load_dotenv(dotenv_path=env_path)

    # API Key 是唯一必须手动配置的项
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "\n错误：缺少 OPENAI_API_KEY\n"
            "\n解决方法：\n"
            "  1. 复制 .env.example 为 .env\n"
            "  2. 填入你的 API Key\n"
            "  3. 重新运行\n"
        )


# ═══════════════════════════════════════════════════════════════════
#  LLM 配置 — 控制模型调用行为
# ═══════════════════════════════════════════════════════════════════

def get_model() -> str:
    """模型名称。国内 API 改为 deepseek-chat 等。"""
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def get_base_url() -> str | None:
    """API 地址。国内 API 设为 https://api.deepseek.com 等。"""
    return os.environ.get("OPENAI_BASE_URL") or None


def get_llm_timeout() -> int:
    """单次 LLM 调用的超时秒数，超时会自动重试。"""
    return _env_int("LLM_TIMEOUT", 30)


def get_llm_max_retries() -> int:
    """LLM 调用失败后的最大重试次数（指数退避：1s→2s→4s）。"""
    return _env_int("LLM_MAX_RETRIES", 3)


# ═══════════════════════════════════════════════════════════════════
#  安全配置 — 防滥用、防注入
# ═══════════════════════════════════════════════════════════════════

def get_max_input_length() -> int:
    """用户单次输入的最大字符数，防止超长输入耗尽 token。"""
    return _env_int("MAX_INPUT_LENGTH", 2000)


def get_max_tool_calls_per_turn() -> int:
    """同一工具在同一轮对话中的最大调用次数，防止单工具滥用。"""
    return _env_int("MAX_TOOL_CALLS_PER_TURN", 5)


def get_max_tool_calls_total() -> int:
    """一轮对话中所有工具的总调用次数上限。"""
    return _env_int("MAX_TOOL_CALLS_TOTAL", 15)


def is_injection_check_enabled() -> bool:
    """是否启用 prompt 注入检测（正则匹配中英文注入模式）。"""
    return os.environ.get("ENABLE_INJECTION_CHECK", "true").strip().lower() in ("true", "1", "yes")


# ═══════════════════════════════════════════════════════════════════
#  Agent 配置 — 控制推理行为
# ═══════════════════════════════════════════════════════════════════

def get_max_steps() -> int:
    """ReAct 循环的最大推理步数（每步可调一次工具或给出答案）。"""
    return _env_int("MAX_STEPS", 5)


def get_max_memory() -> int:
    """短期记忆保留的最大消息条数，超出后丢弃最早的消息。"""
    return _env_int("MAX_MEMORY", 30)


def is_debug() -> bool:
    """调试模式：控制台显示详细日志（LLM 原始响应、工具调用详情等）。"""
    return os.environ.get("DEBUG", "").strip().lower() in ("1", "true", "yes")
