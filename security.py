"""
安全模块 — 在 Agent 的输入和输出两端提供防护。

职责：
1. 输入检测：拦截超长输入和 prompt 注入攻击
2. 输出脱敏：过滤 LLM 回复中可能泄露的 API Key、Token 等
3. 工具频率限制：防止 Agent 陷入死循环反复调用工具
"""
import re
from config import get_max_input_length, is_injection_check_enabled


# ═══════════════════════════════════════════════════════════════════
#  Prompt 注入检测
#  用正则匹配常见注入话术（中英文），命中即视为可疑。
#  这是第一道防线，不是万能的，但能挡住大部分低级攻击。
# ═══════════════════════════════════════════════════════════════════

_INJECTION_PATTERNS = [
    # 中文注入模式
    r"忽略(之前|上面|所有)(的)?(指令|规则|提示)",
    r"你现在(是|扮演|变成)",
    r"无视(之前|上面|所有)(的)?(指令|规则)",
    r"你的(指令|规则|提示)是",
    # 英文注入模式
    r"ignore\s+(previous|above|all)\s+(instructions?|rules?)",
    r"you\s+are\s+now\s+",
    r"system\s*prompt",
    r"reveal\s+(your|the)\s+(system|prompt|instructions?)",
    r"repeat\s+(the|your)\s+(system|prompt)",
    r"override\s+(safety|rules?|instructions?)",
    r"DAN\s*mode",
    r"jailbreak",
]

# 预编译正则，避免每次调用都重新编译
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def check_injection(text: str) -> bool:
    """
    检测文本是否包含 prompt 注入特征。
    返回 True 表示可疑，应拒绝该输入。
    """
    if not is_injection_check_enabled():
        return False
    return bool(_INJECTION_RE.search(text))


# ═══════════════════════════════════════════════════════════════════
#  输入验证
#  在用户输入进入 LLM 之前做检查，不合格直接拦截。
# ═══════════════════════════════════════════════════════════════════

def validate_input(text: str) -> tuple[bool, str]:
    """
    验证用户输入是否合法。
    返回 (is_valid, error_message)，合法时 error_message 为空。
    """
    max_len = get_max_input_length()

    # 空输入
    if not text or not text.strip():
        return False, "输入不能为空"

    # 超长输入 — 防止一次性塞入大量文本耗尽 token 预算
    if len(text) > max_len:
        return False, f"输入超过最大长度限制（{max_len} 字符）"

    # prompt 注入检测
    if check_injection(text):
        return False, "检测到可能的 prompt 注入，已拒绝"

    return True, ""


# ═══════════════════════════════════════════════════════════════════
#  输出脱敏
#  LLM 回复可能意外包含 API Key、Token 等敏感信息，
#  在展示给用户之前用正则替换掉。
# ═══════════════════════════════════════════════════════════════════

_SANITIZE_PATTERNS = [
    # OpenAI 风格的 API Key: sk-xxxxx
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[API_KEY_REDACTED]"),
    # .env 格式的 Key 赋值
    (re.compile(r"OPENAI_API_KEY\s*=\s*\S+"), "OPENAI_API_KEY=[REDACTED]"),
    # Bearer Token
    (re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}"), "Bearer [TOKEN_REDACTED]"),
]


def sanitize_output(text: str) -> str:
    """过滤输出中的敏感信息（API Key、Token 等）。"""
    for pattern, replacement in _SANITIZE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ═══════════════════════════════════════════════════════════════════
#  工具调用频率限制
#  防止 Agent 陷入死循环反复调用同一个工具，
#  或者被恶意输入诱导无限调用工具。
# ═══════════════════════════════════════════════════════════════════

class ToolCallLimiter:
    """
    工具调用计数器，支持两级限制：
    - max_per_turn: 同一工具在本轮对话中的最大调用次数
    - max_total: 所有工具在本轮对话中的总调用次数
    """

    def __init__(self, max_per_turn: int = 5, max_total: int = 15) -> None:
        self.max_per_turn = max_per_turn
        self.max_total = max_total
        self._turn_count: dict[str, int] = {}  # 每个工具本轮调用次数
        self._total_count: int = 0              # 所有工具总调用次数

    def can_call(self, tool_name: str) -> tuple[bool, str]:
        """检查是否允许调用该工具。返回 (allowed, reason)。"""
        # 总次数上限
        if self._total_count >= self.max_total:
            return False, f"工具调用总次数已达上限（{self.max_total}）"

        # 单工具次数上限
        count = self._turn_count.get(tool_name, 0)
        if count >= self.max_per_turn:
            return False, f"工具 {tool_name} 本轮调用已达上限（{self.max_per_turn}）"

        return True, ""

    def record_call(self, tool_name: str) -> None:
        """记录一次成功的工具调用。"""
        self._turn_count[tool_name] = self._turn_count.get(tool_name, 0) + 1
        self._total_count += 1

    def reset_turn(self) -> None:
        """重置本轮计数（每轮用户输入开始时调用）。同时重置总次数。"""
        self._turn_count.clear()
        self._total_count = 0

    def reset_all(self) -> None:
        """重置所有计数（清除记忆时调用）。"""
        self._turn_count.clear()
        self._total_count = 0

    @property
    def total_calls(self) -> int:
        """本轮对话已发生的总工具调用次数。"""
        return self._total_count
