"""
任务规划器 — 将复杂任务拆解为可执行的步骤列表。

使用场景：用户通过 /plan 命令发起复杂任务时，
先让 LLM 把任务分解成 3-6 个步骤，每个步骤标明是否需要工具，
然后由 executor.py 逐步执行。

示例输入：/plan 帮我调研最近 AI 编程工具的发展动态
示例输出：
  目标：调研 AI 编程工具发展动态
  步骤 1：搜索最新 AI 编程工具新闻（工具：web_search）
  步骤 2：整理搜索结果，提取关键信息（无工具）
  步骤 3：生成简要报告（无工具）
"""
import json
import re

from llm import chat

# 规划专用的 system prompt — 告诉 LLM 它的角色和输出格式
PLANNER_PROMPT = """你是一个任务规划专家。

用户给你一个复杂任务，把它分解成 3-6 个清晰、可执行的步骤。

可用工具：web_search（搜索）、dns_lookup（DNS查询）、scan_ports（端口扫描）、check_password（密码检查）、cve_lookup（CVE漏洞查询）、ip_info（IP信息查询）

要求：
- 每步要具体，能直接执行
- 需要工具的步骤标明工具名，不需要的填 null
- 步骤数控制在 3-6 步

只返回 JSON，不要加任何其他文字：
{
  "goal": "任务总目标一句话描述",
  "steps": [
    {"step": 1, "description": "具体步骤描述", "tool": "工具名或null"},
    {"step": 2, "description": "具体步骤描述", "tool": "工具名或null"}
  ]
}"""


def make_plan(task: str) -> dict:
    """
    为任务生成执行计划。

    返回格式：
    {
        "goal": "任务总目标",
        "steps": [
            {"step": 1, "description": "步骤描述", "tool": "工具名或null"},
            ...
        ]
    }
    """
    response = chat([
        {"role": "system", "content": PLANNER_PROMPT},
        {"role": "user", "content": f"请为这个任务制定执行计划：{task}"},
    ])

    # 解析 LLM 返回的 JSON（容错处理）
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # 解析失败时，返回一个单步计划作为兜底
    return {"goal": task, "steps": [{"step": 1, "description": task, "tool": None}]}


def print_plan(plan: dict) -> None:
    """将执行计划格式化输出到控制台。"""
    print(f"\n目标：{plan.get('goal', '未知')}")
    steps = plan.get("steps", [])
    print(f"共 {len(steps)} 步：")
    for i, s in enumerate(steps, 1):
        step_num = s.get("step", i)
        desc = s.get("description", "（无描述）")
        tool_hint = f"  （工具：{s['tool']}）" if s.get("tool") else ""
        print(f"  步骤 {step_num}：{desc}{tool_hint}")
