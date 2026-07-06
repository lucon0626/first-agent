"""
CVE 漏洞查询工具 — 查询 NVD 漏洞库获取漏洞详情。

用途：
- 漏洞评估：查询 CVE 的 CVSS 评分、影响范围
- 安全通报：获取漏洞描述和参考链接
- 资产风险：了解漏洞影响的产品和版本

API：NVD (National Vulnerability Database) 2.0，免费，不需要 Key。
"""
import re
import requests


def cve_lookup(cve_id: str) -> str:
    """
    查询 CVE 漏洞详情。

    参数:
        cve_id: CVE 编号，格式为 CVE-YYYY-NNNNN，如 "CVE-2021-44228"

    返回:
        漏洞描述、CVSS 评分、影响产品、参考链接
    """
    cve_id = cve_id.strip().upper()

    # 格式校验
    if not re.match(r"^CVE-\d{4}-\d{4,}$", cve_id):
        return f"CVE 编号格式错误：{cve_id}，正确格式为 CVE-YYYY-NNNNN"

    try:
        resp = requests.get(
            "https://services.nvd.nist.gov/rest/json/cves/2.0",
            params={"cveId": cve_id},
            timeout=15,
        )

        if resp.status_code == 404:
            return f"未找到漏洞：{cve_id}"

        if resp.status_code == 403:
            return "NVD API 请求频率超限，请稍后重试（免费限制 5 次/30 秒）"

        resp.raise_for_status()
        data = resp.json()

        vulnerabilities = data.get("vulnerabilities", [])
        if not vulnerabilities:
            return f"未找到漏洞：{cve_id}"

        cve = vulnerabilities[0].get("cve", {})

        # 基本信息
        lines = [f"漏洞详情：{cve_id}\n{'─'*50}"]

        # 描述（优先取中文，其次英文）
        descriptions = cve.get("descriptions", [])
        desc_en = next((d.get("value", "") for d in descriptions if d.get("lang") == "en"), "")
        desc_cn = next((d.get("value", "") for d in descriptions if d.get("lang") == "zh"), "")
        desc = desc_cn or desc_en
        if desc:
            # 截断过长的描述
            if len(desc) > 500:
                desc = desc[:500] + "..."
            lines.append(f"\n描述：\n{desc}")

        # CVSS 评分
        metrics = cve.get("metrics", {})
        cvss_info = _extract_cvss(metrics)
        if cvss_info:
            lines.append(f"\nCVSS 评分：")
            lines.append(f"  分数：{cvss_info['score']}")
            lines.append(f"  严重度：{cvss_info['severity']}")
            if cvss_info.get("vector"):
                lines.append(f"  向量：{cvss_info['vector']}")

        # 影响产品
        affected = _extract_affected(cve)
        if affected:
            lines.append(f"\n影响产品（前10条）：")
            for product in affected[:10]:
                lines.append(f"  - {product}")

        # 发布和修改时间
        published = cve.get("published", "")[:10]
        modified = cve.get("lastModified", "")[:10]
        if published:
            lines.append(f"\n发布时间：{published}")
        if modified:
            lines.append(f"修改时间：{modified}")

        # 参考链接
        references = cve.get("references", [])
        if references:
            lines.append(f"\n参考链接（前5条）：")
            for ref in references[:5]:
                url = ref.get("url", "")
                tags = ", ".join(ref.get("tags", []))
                lines.append(f"  - {url}")
                if tags:
                    lines.append(f"    标签：{tags}")

        return "\n".join(lines)

    except requests.Timeout:
        return f"NVD API 查询超时，请稍后重试"
    except requests.RequestException as e:
        return f"NVD API 请求失败：{e}"
    except Exception as e:
        return f"查询出错：{e}"


def _extract_cvss(metrics: dict) -> dict | None:
    """从 metrics 中提取 CVSS 评分信息。"""
    # 优先取 CVSS 3.1，其次 3.0，最后 2.0
    for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
        metric_list = metrics.get(key, [])
        if metric_list:
            metric = metric_list[0]
            cvss = metric.get("cvssData", {})
            return {
                "score": cvss.get("baseScore", "N/A"),
                "severity": cvss.get("baseSeverity", "N/A"),
                "vector": cvss.get("vectorString", ""),
            }
    return None


def _extract_affected(cve: dict) -> list[str]:
    """提取受影响的产品列表。"""
    products = []
    configurations = cve.get("configurations", [])
    for config in configurations:
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                criteria = match.get("criteria", "")
                # cpe:2.3:a:vendor:product:version:...
                parts = criteria.split(":")
                if len(parts) >= 5:
                    vendor = parts[3]
                    product = parts[4]
                    version = parts[5] if len(parts) > 5 and parts[5] != "*" else ""
                    entry = f"{vendor}/{product}"
                    if version:
                        entry += f" {version}"
                    if entry not in products:
                        products.append(entry)
    return products
