"""
工具注册表 — 集中管理所有可用工具。

新增工具只需两步：
1. 在 tools/ 目录下写一个函数（参考现有工具的写法）
2. 在下面的 TOOLS 字典里加一条记录

Agent 通过 get_tools_description() 获取工具列表（给 LLM 看），
通过 execute_tool() 调用具体工具。
"""
from tools.search import web_search
from tools.dns_lookup import dns_lookup
from tools.port_scanner import scan_ports
from tools.password_check import check_password
from tools.cve_lookup import cve_lookup
from tools.ip_info import ip_info

# ── 工具注册表 ───────────────────────────────────────────────────
# 每个工具包含三个字段：
#   function:    工具的 Python 函数
#   description: 工具用途的自然语言描述（会展示给 LLM）
#   parameters:  参数说明（会展示给 LLM，LLM 据此生成调用参数）
TOOLS: dict[str, dict] = {
    "web_search": {
        "function": web_search,
        "description": "搜索互联网信息。适合查找新闻、安全资讯、漏洞公告、厂商公告。",
        "parameters": {"query": "搜索关键词，字符串"},
    },
    "dns_lookup": {
        "function": dns_lookup,
        "description": "查询域名的 DNS 记录（A/MX/TXT/NS/CNAME 等）。用于域名资产排查、SPF/DKIM 配置检查。",
        "parameters": {
            "domain": "域名，字符串，如 example.com",
            "record_type": "记录类型，字符串，默认 A，支持 A/AAAA/MX/TXT/NS/CNAME/SOA/ALL",
        },
    },
    "scan_ports": {
        "function": scan_ports,
        "description": "扫描目标主机的端口开放状态。用于资产摸底、发现不应暴露的服务。",
        "parameters": {
            "host": "IP 地址或域名，字符串",
            "ports": "端口范围，字符串，默认 common。支持：common(常见端口)/web/db/remote，或逗号分隔(80,443)，或范围(1-1024)",
        },
    },
    "check_password": {
        "function": check_password,
        "description": "检查密码强度和是否已泄露。用于安全审计和密码策略检查。",
        "parameters": {"password": "要检查的密码，字符串"},
    },
    "cve_lookup": {
        "function": cve_lookup,
        "description": "查询 CVE 漏洞详情，包括 CVSS 评分、影响产品、参考链接。用于漏洞评估。",
        "parameters": {"cve_id": "CVE 编号，格式 CVE-YYYY-NNNNN，如 CVE-2021-44228"},
    },
    "ip_info": {
        "function": ip_info,
        "description": "查询 IP 地址的地理位置、ASN、ISP 信息。用于安全事件溯源和威胁情报。",
        "parameters": {"ip": "IPv4 地址或域名，字符串"},
    },
}


def get_tools_description() -> str:
    """
    生成工具列表的自然语言描述，注入到 system prompt 中。
    LLM 靠这段文字知道有哪些工具可用、怎么调用。
    """
    lines = ["你有以下工具可以使用：\n"]
    for name, info in TOOLS.items():
        lines.append(f"工具名：{name}")
        lines.append(f"用途：{info['description']}")
        lines.append(f"参数：{info['parameters']}")
        lines.append("")
    return "\n".join(lines)


def execute_tool(tool_name: str, params: dict) -> str:
    """
    根据工具名调用对应的函数。

    错误处理：
    - 工具不存在 → 返回可用工具列表
    - 参数类型错误 → 返回参数说明
    - 其他异常 → 返回错误信息

    所有返回值都转为字符串，方便 LLM 理解。
    """
    if tool_name not in TOOLS:
        available = list(TOOLS.keys())
        return f"没有这个工具：{tool_name!r}，可用工具：{available}"
    try:
        return str(TOOLS[tool_name]["function"](**params))
    except TypeError as e:
        return f"工具参数有误：{e}"
    except Exception as e:
        return f"工具执行出错：{e}"
