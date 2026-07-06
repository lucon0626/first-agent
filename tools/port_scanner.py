"""
端口扫描工具 — 快速检测目标主机的端口开放状态。

用途：
- 资产摸底：确认服务器开放了哪些服务
- 安全检查：发现不应开放的端口（如 3389、6379 对外暴露）
- 服务发现：识别运行中的服务类型

注意：仅用于授权范围内的安全检查，不要扫描未授权的目标。
"""
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

# 常见端口 → 服务名映射
_PORT_SERVICES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    9090: "WebConsole", 27017: "MongoDB",
}

# 预设端口组
_PRESETS = {
    "common": list(_PORT_SERVICES.keys()),
    "web": [80, 443, 8080, 8443],
    "db": [1433, 1521, 3306, 5432, 6379, 27017],
    "remote": [22, 23, 3389, 5900],
}


def _parse_ports(ports: str) -> list[int]:
    """
    解析端口参数，支持多种格式：
    - "common" / "web" / "db" / "remote" → 预设端口组
    - "80,443,8080" → 逗号分隔
    - "1-1024" → 范围
    """
    ports = ports.strip().lower()

    # 预设
    if ports in _PRESETS:
        return _PRESETS[ports]

    result = set()
    for part in ports.split(","):
        part = part.strip()
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                start, end = int(start), int(end)
                if 1 <= start <= 65535 and 1 <= end <= 65535 and start <= end:
                    result.update(range(start, min(end + 1, start + 1025)))  # 限制范围
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= 65535:
                    result.add(p)
            except ValueError:
                continue

    return sorted(result) if result else []


def _check_port(host: str, port: int, timeout: float = 1.0) -> tuple[int, bool]:
    """检测单个端口是否开放。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            return port, result == 0
    except Exception:
        return port, False


def scan_ports(host: str, ports: str = "common") -> str:
    """
    扫描目标主机的端口开放状态。

    参数:
        host: IP 地址或域名
        ports: 端口范围，支持：
               - 预设组: "common"(常见端口) / "web" / "db" / "remote"
               - 逗号分隔: "80,443,8080"
               - 范围: "1-1024"

    返回:
        开放端口列表及对应服务名
    """
    host = host.strip()
    if not host:
        return "主机地址不能为空"

    # 去掉协议前缀
    for prefix in ("http://", "https://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    host = host.split("/")[0].split(":")[0]

    port_list = _parse_ports(ports)
    if not port_list:
        return "未指定有效端口。支持格式：common/web/db/remote，或逗号分隔(80,443)，或范围(1-1024)"

    # 解析域名 → IP
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        return f"无法解析主机：{host}"

    # 并发扫描（最多 50 线程）
    open_ports = []
    with ThreadPoolExecutor(max_workers=min(50, len(port_list))) as executor:
        futures = {executor.submit(_check_port, ip, port): port for port in port_list}
        for future in as_completed(futures):
            port, is_open = future.result()
            if is_open:
                service = _PORT_SERVICES.get(port, "未知")
                open_ports.append((port, service))

    open_ports.sort(key=lambda x: x[0])

    if not open_ports:
        return f"主机 {host}（{ip}）在扫描的 {len(port_list)} 个端口中未发现开放端口"

    lines = [f"主机 {host}（{ip}）开放端口：\n"]
    for port, service in open_ports:
        lines.append(f"  {port:>5}  {service}")

    lines.append(f"\n共扫描 {len(port_list)} 个端口，{len(open_ports)} 个开放")

    # 安全提醒
    risky_ports = {3389: "RDP", 6379: "Redis", 27017: "MongoDB", 23: "Telnet"}
    warnings = []
    for port, service in open_ports:
        if port in risky_ports:
            warnings.append(f"  [!] {port}（{risky_ports[port]}）对外暴露，建议检查是否必要")
    if warnings:
        lines.append("\n安全提醒：")
        lines.extend(warnings)

    return "\n".join(lines)
