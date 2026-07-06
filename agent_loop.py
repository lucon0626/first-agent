"""
ReAct Agent — 实现 "思考 → 行动 → 观察" 循环。

ReAct（Reasoning + Acting）是 Agent 的核心模式：
1. 用户提出问题
2. Agent 思考：需要调用什么工具？
3. Agent 执行工具，拿到结果
4. Agent 观察结果，决定下一步：继续调工具 or 给出最终答案

这个模块实现了完整的 ReAct 循环，并集成了：
- 安全检查（输入验证、输出脱敏、工具频率限制）
- 对话记忆（多轮对话上下文保持）
- 结构化日志
"""
import json
import re

from llm import chat
from tool_registry import get_tools_description, execute_tool
from memory.short_term import ShortTermMemory
from security import validate_input, sanitize_output, ToolCallLimiter
from config import get_max_steps, get_max_memory, get_max_tool_calls_per_turn, get_max_tool_calls_total
import logger

# ── System Prompt ────────────────────────────────────────────────
# 告诉 LLM 它有哪些工具、必须用 JSON 格式回复、以及三种响应类型。
# {tools_description} 和 {max_steps} 在初始化时会被实际值替换。
REACT_SYSTEM_PROMPT = """你是一个智能助手，拥有对话记忆，可以使用工具完成任务。

{tools_description}
每次回复必须是 JSON，三种格式之一：

1. 需要使用工具：
{{"type": "tool_call", "tool": "工具名", "params": {{"参数名": "参数值"}}, "thought": "我为什么要用这个工具"}}

2. 任务完成或可以直接回答：
{{"type": "final_answer", "content": "回答内容"}}

3. 需要向用户提问：
{{"type": "ask_user", "question": "你的问题"}}

规则：
- 最多使用工具 {max_steps} 次
- 收集到足够信息后，必须给出 final_answer
- 不要用相同参数重复调用同一个工具
- 参数名必须用英文，和工具定义完全一致
- 只返回 JSON，不加任何解释"""


def _safe_parse(text: str) -> dict:
    """
    安全解析 LLM 返回的 JSON。
    LLM 有时会在 JSON 前后加多余文字，这里做容错处理：
    1. 先尝试直接解析整个文本
    2. 失败则用正则提取第一个 {...} 块
    3. 都失败则把原文当作最终答案返回
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 用正则提取 JSON 块（非贪婪，避免匹配多个对象时取过宽）
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            # 非贪婪可能截断了嵌套 JSON，回退到贪婪再试一次
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

    # 都失败了，当作纯文本回答
    return {"type": "final_answer", "content": text}


class ReactAgent:
    """
    带对话记忆的 ReAct Agent。

    核心流程：run(user_input) → 多步推理 → 返回最终答案
    跨轮对话：同一个 Agent 实例的多次 run() 调用共享记忆
    安全防护：输入验证 → 工具频率限制 → 输出脱敏
    """

    def __init__(self, max_steps: int | None = None) -> None:
        # 推理步数上限（每步可调一次工具或给出答案）
        self.max_steps = max_steps or get_max_steps()

        # 短期记忆：保留最近 N 条对话，超出后丢弃最早的
        self._memory = ShortTermMemory(max_messages=get_max_memory())

        # 工具调用频率限制器
        self._limiter = ToolCallLimiter(
            max_per_turn=get_max_tool_calls_per_turn(),
            max_total=get_max_tool_calls_total(),
        )

        # 注入 system prompt（包含工具描述和步数限制）
        self._memory.add("system", REACT_SYSTEM_PROMPT.format(
            tools_description=get_tools_description(),
            max_steps=self.max_steps,
        ))

    def run(self, user_input: str) -> str:
        """
        处理一条用户输入，返回最终回答。

        流程：
        1. 验证输入（长度、注入检测）
        2. 进入 ReAct 循环（最多 max_steps 步）
        3. 每步：LLM 思考 → 解析响应 → 执行动作
        4. 返回 final_answer 或达到步数上限后强制收尾
        """
        # ── 第一步：输入验证 ──────────────────
        is_valid, err_msg = validate_input(user_input)
        if not is_valid:
            logger.log_security_event("input_rejected", err_msg)
            return f"⚠️ {err_msg}"

        # 将用户输入加入记忆
        self._memory.add("user", user_input)
        # 重置本轮工具调用计数
        self._limiter.reset_turn()

        # ── 第二步：ReAct 循环 ────────────────
        for step in range(1, self.max_steps + 1):
            logger.debug(f"── 步骤 {step}/{self.max_steps} ──")

            # 调用 LLM，让它决定下一步行动
            ai_response = chat(self._memory.to_api_format())
            logger.debug(f"AI 原始响应: {ai_response[:300]}")
            self._memory.add("assistant", ai_response)

            # 解析 LLM 的 JSON 响应
            decision = _safe_parse(ai_response)
            resp_type = decision.get("type")

            # ── 情况 A：任务完成 ──────────────
            if resp_type == "final_answer":
                answer = decision.get("content", "（无内容）")
                answer = sanitize_output(answer)  # 脱敏后再返回
                logger.info(f"回答完成，共 {step} 步，工具调用 {self._limiter.total_calls} 次")
                return answer

            # ── 情况 B：需要调用工具 ──────────
            if resp_type == "tool_call":
                tool_name = decision.get("tool", "")
                params = decision.get("params", {})
                thought = decision.get("thought", "")

                # 频率限制检查
                allowed, reason = self._limiter.can_call(tool_name)
                if not allowed:
                    logger.log_security_event("tool_limit", reason)
                    # 告诉 LLM 被限制了，让它直接给答案
                    self._memory.add("user", f"工具调用被限制：{reason}。请直接给出最终答案。")
                    continue

                logger.debug(f"调用工具: {tool_name}({params})")
                if thought:
                    logger.debug(f"理由: {thought}")

                # 执行工具
                result = execute_tool(tool_name, params)
                self._limiter.record_call(tool_name)
                logger.log_tool_call(tool_name, params, result, "出错" not in result)

                # 将工具结果加入记忆，让 LLM 继续推理
                self._memory.add("user", f"工具 {tool_name} 返回：\n{result}")
                continue

            # ── 情况 C：需要向用户提问 ────────
            if resp_type == "ask_user":
                question = decision.get("question", "")
                try:
                    answer = input(f"\nAgent 问你：{question}\n你：")
                except (KeyboardInterrupt, EOFError):
                    answer = "用户取消了回答"
                self._memory.add("user", answer)
                continue

            # ── 未知响应类型，当作最终答案 ────
            return sanitize_output(str(decision))

        # ── 第三步：步数用完，强制收尾 ────────
        logger.warning(f"达到步骤上限 ({self.max_steps})，强制收尾")
        self._memory.add("user", "已达步骤上限，请立即给出最终答案。")
        final = chat(self._memory.to_api_format())
        parsed = _safe_parse(final)
        answer = sanitize_output(parsed.get("content", final))
        self._memory.add("assistant", answer)
        return answer

    def clear_memory(self) -> None:
        """清除对话记忆和工具调用计数（保留 system prompt）。"""
        self._memory.clear_non_system()
        self._limiter.reset_all()
        logger.info("记忆已清除")

    def memory_count(self) -> int:
        """返回当前记忆中的非 system 消息条数。"""
        return self._memory.count()
