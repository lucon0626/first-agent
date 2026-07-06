"""
IP 信息查询工具 — 查询 IP 地址的地理位置、ASN、ISP 信息。

用途：
- 安全事件溯源：确认可疑 IP 的归属地和运营商
- 威胁情报：判断 IP 是否来自高风险地区
- 资产管理：了解服务器 IP 的网络归属

API：ip-api.com，免费，不需要 Key，限制 45 次/分钟。
"""
import ipaddress
import socket
import requests


def _is_valid_ip(ip: str) -> bool:
    """用 ipaddress 模块做严格的 IPv4 格式校验。"""
    try:
        addr = ipaddress.ip_address(ip)
        return isinstance(addr, ipaddress.IPv4Address)
    except ValueError:
        return False


def _is_special_ip(ip: str) -> str | None:
    """
    判断是否为特殊用途 IP（私有、回环、广播等）。
    返回说明文字，或 None 表示公网 IP。
    """
    try:
        addr = ipaddress.ip_address(ip)
        # 按优先级检查，更具体的放前面
        if addr.is_loopback:
            return "回环地址"
        if addr.is_link_local:
            return "链路本地地址"
        if addr.is_multicast:
            return "组播地址"
        if addr.is_unspecified:
            return "未指定地址"
        if addr.is_reserved:
            return "保留地址"
        if addr.is_private:
            return "私有地址"
        return None
    except ValueError:
        return None


def ip_info(ip: str) -> str:
    """
    查询 IP 地址的详细信息。

    参数:
        ip: IPv4 地址，或域名（会自动解析）

    返回:
        地理位置、ASN、ISP、经纬度等信息
    """
    ip = ip.strip()
    if not ip:
        return "IP 地址不能为空"

    # 去掉协议前缀和路径
    for prefix in ("http://", "https://"):
        if ip.startswith(prefix):
            ip = ip[len(prefix):]
    ip = ip.split("/")[0].split(":")[0]

    # 如果是域名，先解析为 IP
    if not _is_valid_ip(ip):
        try:
            ip = socket.gethostbyname(ip)
        except socket.gaierror:
            return f"无法解析：{ip}"

    # 特殊 IP 检查
    special = _is_special_ip(ip)
    if special:
        return f"{ip} 是{special}，无法查询公网信息"

    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={
                "fields": "status,message,country,countryCode,region,regionName,city,"
                          "zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "fail":
            return f"查询失败：{data.get('message', '未知错误')}"

        lines = [f"IP 信息：{ip}\n{'─'*40}"]

        # 地理位置
        location_parts = []
        if data.get("country"):
            location_parts.append(data["country"])
        if data.get("regionName"):
            location_parts.append(data["regionName"])
        if data.get("city"):
            location_parts.append(data["city"])
        if location_parts:
            lines.append(f"位置：{' / '.join(location_parts)}")

        if data.get("zip"):
            lines.append(f"邮编：{data['zip']}")

        if data.get("timezone"):
            lines.append(f"时区：{data['timezone']}")

        # 经纬度
        if data.get("lat") and data.get("lon"):
            lines.append(f"坐标：{data['lat']}, {data['lon']}")

        # 网络信息
        lines.append(f"\n网络信息：")
        if data.get("isp"):
            lines.append(f"  ISP：{data['isp']}")
        if data.get("org"):
            lines.append(f"  组织：{data['org']}")
        if data.get("as"):
            lines.append(f"  ASN：{data['as']}")
        if data.get("asname"):
            lines.append(f"  AS 名称：{data['asname']}")
        if data.get("reverse"):
            lines.append(f"  反向 DNS：{data['reverse']}")

        # 属性标签
        tags = []
        if data.get("mobile"):
            tags.append("移动网络")
        if data.get("proxy"):
            tags.append("代理/VPN")
        if data.get("hosting"):
            tags.append("托管/IDC")
        if tags:
            lines.append(f"\n属性：{', '.join(tags)}")

        return "\n".join(lines)

    except requests.Timeout:
        return f"IP 查询超时，请稍后重试"
    except requests.RequestException as e:
        return f"IP 查询请求失败：{e}"
    except Exception as e:
        return f"查询出错：{e}"
