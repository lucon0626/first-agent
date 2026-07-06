# My First AI Agent

> 用纯 Python 从零搭建一个支持多工具、有记忆、能多步推理的 AI Agent 系统。
> 不依赖 LangChain、AutoGen 或任何 Agent 框架。

## 最终效果

```
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

你：帮我搜索一下最近 AI 领域的新闻

[步骤 1/5]
[调用工具]: web_search，参数：{'query': 'AI 最新新闻'}
[工具结果]: 摘要：...

Agent：根据搜索结果，AI 领域近期有以下重要动态：...
（对话记忆：3 条）

你：/plan 帮我调研 AI 编程工具的发展动态，写一份简要报告

正在制定计划...
目标：调研 AI 编程工具发展动态
共 4 步：
  步骤 1：搜索最新 AI 编程工具新闻  （工具：web_search）
  步骤 2：整理搜索结果，提取关键信息
  步骤 3：搜索用户评价和对比分析  （工具：web_search）
  步骤 4：生成简要报告

确认执行？(y/n)：
```

## 架构

```
用户输入
  │
  ▼
┌─────────────┐
│  安全检查    │ ← 输入长度、prompt 注入检测
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│ ReAct 循环  │────→│  LLM 调用   │ ← 带重试、超时
│ 思考→行动   │     └─────────────┘
│ →观察→思考  │              │
└──────┬──────┘              ▼
       │              ┌─────────────┐
       │              │  工具调用    │ ← 搜索、DNS、端口、密码、CVE、IP
       │              └─────────────┘
       ▼
┌─────────────┐
│  输出脱敏    │ ← 过滤 API Key、Token
└──────┬──────┘
       │
       ▼
    最终回答
```

**核心模块：**

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置中心 | `config.py` | 所有可调参数从环境变量读取 |
| 安全模块 | `security.py` | 输入验证、注入检测、输出脱敏、频率限制 |
| 日志模块 | `logger.py` | 结构化日志，支持 DEBUG 模式 |
| LLM 调用 | `llm.py` | 封装 OpenAI API，带重试和超时 |
| ReAct Agent | `agent_loop.py` | 多步推理循环（思考→行动→观察） |
| 任务规划 | `planner.py` | 将复杂任务拆解为可执行步骤 |
| 计划执行 | `executor.py` | 按计划逐步执行，汇总生成答案 |
| 工具注册 | `tool_registry.py` | 集中管理所有工具 |
| 短期记忆 | `memory/short_term.py` | 对话上下文管理，自动裁剪 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

需要 Python 3.10+。

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```env
OPENAI_API_KEY=sk-你的key
```

**国内 API（不需要翻墙）：**

```env
OPENAI_API_KEY=你的key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

支持 DeepSeek、月之暗面、智谱 AI 等任何兼容 OpenAI 格式的服务。

### 3. 运行

```bash
python main.py
```

## 使用方式

### 对话模式

直接输入问题，Agent 会自动判断是否需要使用工具：

```
你：帮我查一下 example.com 的 DNS 记录
你：扫描 192.168.1.1 的常见端口
你：检查一下密码 P@ssw0rd123 是否安全
你：查一下 CVE-2021-44228 这个漏洞的详情
你：8.8.8.8 这个 IP 是哪里的？
你：搜索一下最近的勒索软件攻击事件
```

### 规划模式

用 `/plan` 让 Agent 先制定计划再执行，适合复杂任务：

```
你：/plan 帮我调研最近 AI 编程工具的发展动态，写一份简要报告
```

Agent 会先生成执行计划，你确认后才会开始执行。

### 其他命令

| 命令 | 说明 |
|------|------|
| `/clear` | 清除对话记忆，开始新对话 |
| `/help` | 显示帮助信息 |
| `/quit` | 退出程序 |

## 内置工具

| 工具 | 说明 | 用途 |
|------|------|------|
| `web_search` | DuckDuckGo 搜索（免费，无需 Key） | 查找安全资讯、漏洞公告 |
| `dns_lookup` | DNS 记录查询（A/MX/TXT/NS/CNAME 等） | 域名资产排查、SPF/DKIM 配置检查 |
| `scan_ports` | 端口扫描（并发、超时控制） | 资产摸底、发现暴露服务 |
| `check_password` | 密码强度检查 + Have I Been Pwned 泄露检查 | 安全审计、密码策略检查 |
| `cve_lookup` | CVE 漏洞查询（NVD API，含 CVSS 评分） | 漏洞评估、安全通报 |
| `ip_info` | IP 信息查询（地理位置、ASN、ISP） | 安全事件溯源、威胁情报 |

### 新增工具

两步即可：

1. 在 `tools/` 下写函数：

```python
# tools/whois_lookup.py
def whois_lookup(domain: str) -> str:
    """查询域名 WHOIS 信息。"""
    # 你的实现
    return result
```

2. 在 `tool_registry.py` 注册：

```python
from tools.whois_lookup import whois_lookup

TOOLS["whois_lookup"] = {
    "function": whois_lookup,
    "description": "查询域名的 WHOIS 注册信息。",
    "parameters": {"domain": "域名，字符串"},
}
```

完成。Agent 下次运行就会自动使用新工具。

## 安全特性

| 特性 | 说明 |
|------|------|
| Prompt 注入检测 | 正则匹配中英文注入模式（"忽略指令"、"you are now" 等） |
| 输入长度限制 | 默认 2000 字符，防 token 耗尽 |
| 输出脱敏 | 自动过滤 API Key、Bearer Token 等敏感信息 |
| 工具频率限制 | 单工具 ≤5 次/轮，总计 ≤15 次，防滥用 |
| 安全计算器 | 用 AST 白名单替代 eval()，只允许四则运算（已移除） |

所有安全参数都可通过 `.env` 调整。

## 配置项

在 `.env` 中设置（都有合理默认值，不设置也能跑）：

```env
# ── LLM ──────────────────────────────
OPENAI_API_KEY=sk-xxx          # 必填
OPENAI_MODEL=gpt-4o-mini       # 模型名
OPENAI_BASE_URL=               # API 地址（国内 API 用）
LLM_TIMEOUT=30                 # 调用超时（秒）
LLM_MAX_RETRIES=3              # 最大重试次数

# ── 安全 ─────────────────────────────
MAX_INPUT_LENGTH=2000          # 输入最大字符数
MAX_TOOL_CALLS_PER_TURN=5      # 单工具每轮最大调用次数
MAX_TOOL_CALLS_TOTAL=15        # 工具总调用次数上限
ENABLE_INJECTION_CHECK=true    # 是否启用注入检测

# ── Agent ────────────────────────────
MAX_STEPS=5                    # ReAct 最大推理步数
MAX_MEMORY=30                  # 短期记忆最大条数

# ── 调试 ─────────────────────────────
DEBUG=false                    # 开启后控制台显示详细日志
```

## 项目结构

```
agent/
├── main.py              # CLI 入口
├── config.py            # 配置中心（环境变量读取）
├── security.py          # 安全模块（注入检测、脱敏、限频）
├── logger.py            # 日志模块（文件 + 控制台）
├── llm.py               # LLM 调用（重试、超时）
├── agent_loop.py        # ReAct 多步推理循环
├── planner.py           # 任务拆解
├── executor.py          # 计划执行
├── tool_registry.py     # 工具注册表
├── memory/
│   ├── __init__.py
│   └── short_term.py    # 短期记忆（自动裁剪）
├── tools/
│   ├── __init__.py
│   ├── search.py        # DuckDuckGo 搜索
│   ├── dns_lookup.py    # DNS 记录查询
│   ├── port_scanner.py  # 端口扫描
│   ├── password_check.py# 密码强度检查
│   ├── cve_lookup.py    # CVE 漏洞查询
│   └── ip_info.py       # IP 信息查询
├── .env.example         # 配置模板
├── .gitignore
└── requirements.txt
```

## 从这个项目能学到什么

- **Agent 的本质**：感知 → 思考 → 行动 → 观察，循环往复
- **ReAct 模式**：让 LLM 边推理边调用工具，而不是一次性输出
- **工具调用**：LLM 输出结构化 JSON → 解析 → 执行 → 结果回传
- **记忆管理**：如何在有限的 token 窗口内保持对话上下文
- **任务规划**：复杂任务先拆解再执行
- **安全防护**：prompt 注入检测、输出脱敏、频率限制

## 之后可以探索

- 添加更多安全工具（WHOIS 查询、邮件头分析、Hash 情报查询）
- 接入威胁情报平台 API（VirusTotal、AbuseIPDB）
- 添加安全报告生成能力（自动生成安全评估报告）
- 做一个 Web 界面（FastAPI + 简单前端）
- 探索多 Agent 协作（多个 Agent 分工配合）

## License

MIT
