"""
结构化日志模块 — 替代 print()，提供分级日志能力。

设计思路：
- 正常运行时，控制台只显示 INFO 级别（关键信息）
- 开启 DEBUG 模式后，控制台显示详细的推理过程
- 所有日志（含 DEBUG）始终写入 agent.log 文件，方便事后排查

使用方式：
  import logger
  logger.info("用户已连接")
  logger.debug("LLM 原始响应: ...")
  logger.log_security_event("injection", "检测到注入尝试")
"""
import logging
import os
import sys

# 日志文件路径（项目根目录下）
_LOG_FILE = "agent.log"

# 从环境变量读取是否开启调试模式
_debug_mode = os.environ.get("DEBUG", "").strip().lower() in ("1", "true", "yes")

# ── 日志格式 ─────────────────────────────────────────────────────
# 文件格式：带时间戳和级别，方便筛选
_FILE_FMT = "%(asctime)s | %(levelname)-7s | %(message)s"
# 控制台格式：简洁，只显示消息内容
_CONSOLE_FMT = "%(message)s"

# ── Logger 初始化 ────────────────────────────────────────────────
_logger = logging.getLogger("agent")
_logger.setLevel(logging.DEBUG)

# 文件 handler — 始终记录所有级别的日志
_fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter(_FILE_FMT))
_logger.addHandler(_fh)

# 控制台 handler — DEBUG 模式下显示全部，否则只显示 INFO 及以上
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.DEBUG if _debug_mode else logging.INFO)
_ch.setFormatter(logging.Formatter(_CONSOLE_FMT))
_logger.addHandler(_ch)


# ═══════════════════════════════════════════════════════════════════
#  基础日志接口 — 对应 Python logging 的四个级别
# ═══════════════════════════════════════════════════════════════════

def debug(msg: str) -> None:
    """调试信息：LLM 原始响应、工具调用详情等。仅 DEBUG 模式在控制台显示。"""
    _logger.debug(msg)


def info(msg: str) -> None:
    """关键信息：配置摘要、回答完成等。始终在控制台显示。"""
    _logger.info(msg)


def warning(msg: str) -> None:
    """警告：重试、步骤上限等。"""
    _logger.warning(msg)


def error(msg: str) -> None:
    """错误：调用失败、认证异常等。"""
    _logger.error(msg)


def is_debug() -> bool:
    """当前是否为调试模式。"""
    return _debug_mode


# ═══════════════════════════════════════════════════════════════════
#  业务日志接口 — 记录特定事件的结构化信息
# ═══════════════════════════════════════════════════════════════════

def log_llm_call(model: str, messages_count: int, response: str, tokens_used: int | None = None) -> None:
    """记录一次 LLM 调用：用了什么模型、多少条消息、回复多长、消耗多少 token。"""
    token_info = f", tokens={tokens_used}" if tokens_used else ""
    debug(f"LLM call: model={model}, msgs={messages_count}, resp_len={len(response)}{token_info}")


def log_tool_call(tool_name: str, params: dict, result: str, success: bool) -> None:
    """记录一次工具调用：工具名、参数、结果摘要、是否成功。"""
    status = "OK" if success else "FAIL"
    preview = result[:200] + "..." if len(result) > 200 else result
    debug(f"Tool [{status}]: {tool_name}({params}) → {preview}")


def log_security_event(event_type: str, detail: str) -> None:
    """记录安全事件（注入拦截、工具限制等），以 WARNING 级别输出。"""
    warning(f"SECURITY [{event_type}]: {detail}")
