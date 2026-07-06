"""
短期记忆模块 — 管理对话上下文。

Agent 的"记忆"本质就是一个消息列表，每次调用 LLM 时把它发过去。
为了防止消息列表无限增长导致超出模型的 token 限制，
这里实现了自动裁剪：只保留最近的 N 条非 system 消息。

消息类型：
- system:    系统提示（定义 Agent 的角色和行为规则），永远不会被裁剪
- user:      用户输入或工具返回结果
- assistant: LLM 的回复
"""
from dataclasses import dataclass, field
from typing import Literal

# 消息角色类型（只能是这三种之一）
MessageRole = Literal["system", "user", "assistant"]


@dataclass
class Message:
    """单条消息。"""
    role: MessageRole
    content: str


@dataclass
class ShortTermMemory:
    """
    对话短期记忆。

    保留最近 max_messages 条非 system 消息，防止超过模型 token 限制。
    system 消息（角色定义）永远不会被丢弃。

    用法：
        memory = ShortTermMemory(max_messages=20)
        memory.add("system", "你是一个助手")
        memory.add("user", "你好")
        messages = memory.to_api_format()  # 传给 LLM
    """
    max_messages: int = 20
    _messages: list[Message] = field(default_factory=list)

    def add(self, role: MessageRole, content: str) -> None:
        """添加一条消息，自动裁剪超出限制的旧消息。"""
        self._messages.append(Message(role=role, content=content))
        self._trim()

    def _trim(self) -> None:
        """
        裁剪超出限制的非 system 消息。
        策略：从最旧的非 system 消息开始丢弃，直到总数不超过 max_messages。
        """
        non_system = [m for m in self._messages if m.role != "system"]
        while len(non_system) > self.max_messages:
            # 找到第一条非 system 消息并移除
            for i, msg in enumerate(self._messages):
                if msg.role != "system":
                    self._messages.pop(i)
                    break
            non_system = [m for m in self._messages if m.role != "system"]

    def to_api_format(self) -> list[dict]:
        """
        转换为 OpenAI API 要求的格式。
        返回：[{"role": "user", "content": "你好"}, ...]
        """
        return [{"role": m.role, "content": m.content} for m in self._messages]

    def clear_non_system(self) -> None:
        """清除所有非 system 消息（保留角色定义）。"""
        self._messages = [m for m in self._messages if m.role == "system"]

    def count(self) -> int:
        """返回非 system 消息的条数（用户可见的对话轮次）。"""
        return len([m for m in self._messages if m.role != "system"])
