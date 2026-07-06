"""
AI Agent 系统入口 — 提供命令行交互界面。

支持的命令：
  直接输入     → 对话模式（ReAct 推理，有记忆，自动使用工具）
  /plan <任务> → 规划模式（先制定计划，确认后逐步执行）
  /clear       → 清除对话记忆
  /help        → 显示帮助
  /quit        → 退出
"""
from config import (
    load_config, get_model, get_base_url,
    get_max_steps, get_max_input_length,
    get_max_tool_calls_per_turn, get_max_tool_calls_total,
    is_injection_check_enabled, is_debug,
)
from agent_loop import ReactAgent
from planner import make_plan, print_plan
from executor import execute_plan
from security import validate_input
import logger


# 启动时显示的横幅
BANNER = """
=================================================
    我的 AI Agent 系统 v1.1
=================================================
命令：
  直接输入     → 对话模式（有记忆，自动使用工具）
  /plan <任务> → 规划模式（先制定计划再执行）
  /clear       → 清除对话记忆，开始新对话
  /help        → 显示帮助
  /quit        → 退出
=================================================
"""

# /help 命令的详细说明
HELP_TEXT = """
命令说明：
  直接输入任何问题  → Agent 会判断是否用工具，有对话记忆
  /plan <任务描述>  → 先生成执行计划（你可以确认后再执行）
  /clear            → 清除对话记忆
  /help             → 显示本帮助

示例：
  你：北京今天天气怎样，适合跑步吗？
  你：帮我计算 (1234 + 5678) * 3
  你：/plan 帮我调研最近 AI 编程工具的发展动态，写一份简要报告
"""


def _print_config_summary() -> None:
    """启动时显示当前配置摘要，让用户知道系统处于什么状态。"""
    model = get_model()
    base_url = get_base_url() or "默认"
    injection = "✓" if is_injection_check_enabled() else "✗"
    debug = "✓" if is_debug() else "✗"

    logger.info(f"模型: {model}")
    logger.info(f"API 地址: {base_url}")
    logger.info(f"安全: 注入检测={injection}, 输入限制={get_max_input_length()}字符")
    logger.info(f"工具限制: 单工具{get_max_tool_calls_per_turn()}次/轮, 总计{get_max_tool_calls_total()}次")
    logger.info(f"推理步数: 最大{get_max_steps()}步")
    logger.info(f"调试模式: {debug}")
    logger.info("")


def main() -> None:
    """主循环：读取用户输入 → 分发到对应处理逻辑。"""
    # 加载配置（检查 API Key 等）
    load_config()
    print(BANNER)
    _print_config_summary()

    # 创建 Agent 实例（跨对话共享记忆）
    agent = ReactAgent()

    while True:
        # 读取用户输入（支持 Ctrl+C 优雅退出）
        try:
            user_input = input("你：").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue

        # ── /quit — 退出程序 ──────────────────
        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("再见！")
            break

        # ── /help — 显示帮助 ──────────────────
        if user_input.lower() == "/help":
            print(HELP_TEXT)
            continue

        # ── /clear — 清除记忆 ─────────────────
        if user_input.lower() == "/clear":
            agent.clear_memory()
            print("记忆已清除，开始新对话。\n")
            continue

        # ── /plan — 规划模式 ──────────────────
        if user_input.lower().startswith("/plan "):
            task = user_input[6:].strip()
            if not task:
                print("用法：/plan 你的任务描述\n")
                continue

            # 输入验证
            is_valid, err_msg = validate_input(task)
            if not is_valid:
                print(f"⚠️ {err_msg}\n")
                continue

            print("\n正在制定计划...")
            try:
                # 生成计划
                plan = make_plan(task)
                print_plan(plan)

                # 等待用户确认
                try:
                    confirm = input("\n确认执行？(y/n)：").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    print("\n已取消。\n")
                    continue

                if confirm == "y":
                    # 执行计划
                    result = execute_plan(plan)
                    print(f"\nAgent：{result}\n")
                else:
                    print("已取消。\n")
            except Exception as e:
                logger.error(f"规划模式出错: {e}")
                print(f"⚠️ 执行出错，请重试。\n")
            continue

        # ── 普通对话 — ReAct 模式 ─────────────
        try:
            result = agent.run(user_input)
            print(f"\nAgent：{result}")
            print(f"（对话记忆：{agent.memory_count()} 条）\n")
        except KeyboardInterrupt:
            print("\n（已中断）\n")
        except Exception as e:
            logger.error(f"对话出错: {e}")
            print(f"⚠️ 出错了，请重试。\n")


if __name__ == "__main__":
    main()
