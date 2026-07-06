"""
DNS 查询工具 — 查询域名的各类 DNS 记录。

用途：
- 排查域名资产（A/MX/NS/TXT/CNAME）
- 检查 SPF/DKIM/DMARC 配置（TXT 记录）
- 域名接管风险排查（CNAME 指向已失效的服务）

依赖：dnspython
"""
import dns.resolver
import dns.exception


# 支持的记录类型
_VALID_TYPES = {"A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA", "SRV", "CAA"}


def dns_lookup(domain: str, record_type: str = "A") -> str:
    """
    查询域名的 DNS 记录。

    参数:
        domain: 要查询的域名，如 "example.com"
        record_type: 记录类型，支持 A/AAAA/MX/TXT/NS/CNAME/SOA/SRV/CAA/ALL

    返回:
        格式化的 DNS 记录列表
    """
    domain = domain.strip().lower()
    if not domain:
        return "域名不能为空"

    # 去掉协议前缀和路径（用户可能粘贴完整 URL）
    for prefix in ("http://", "https://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.split("/")[0].split(":")[0]

    record_type = record_type.strip().upper()
    if record_type == "ALL":
        types_to_query = ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]
    elif record_type in _VALID_TYPES:
        types_to_query = [record_type]
    else:
        return f"不支持的记录类型：{record_type}，支持：{', '.join(sorted(_VALID_TYPES))}, ALL"

    results = []
    max_records_per_type = 20  # 每种类型最多显示 20 条，防止撑爆上下文

    for rtype in types_to_query:
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=10)  # 10 秒超时
            records = []
            for i, rdata in enumerate(answers):
                if i >= max_records_per_type:
                    records.append(f"  ...（共 {len(list(answers)) + max_records_per_type} 条，仅显示前 {max_records_per_type} 条）")
                    break
                records.append(str(rdata))
            if records:
                results.append(f"【{rtype}】\n  " + "\n  ".join(records))
        except dns.resolver.NoAnswer:
            pass  # 该类型无记录，跳过
        except dns.resolver.NXDOMAIN:
            return f"域名 {domain} 不存在（NXDOMAIN）"
        except dns.exception.Timeout:
            return f"DNS 查询超时：{domain}"
        except Exception as e:
            results.append(f"【{rtype}】查询失败：{e}")

    if results:
        header = f"域名 {domain} 的 DNS 记录：\n"
        return header + "\n".join(results)
    else:
        return f"域名 {domain} 未查询到 {record_type} 记录"
