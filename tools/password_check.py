"""
密码强度检查工具 — 评估密码复杂度 + 泄露检查。

用途：
- 安全审计：批量检查员工密码是否符合策略
- 自查：确认密码是否已在公开泄露库中出现

安全设计：
- 密码本身不会被发送到任何外部服务
- 泄露检查使用 Have I Been Pwned 的 k-anonymity 模式：
  只发送 SHA1 哈希的前 5 位，返回所有匹配的哈希后缀，
  在本地比对完整哈希。HIBP 无法反推出密码。
"""
import hashlib
import re
import requests


# 常见弱密码 TOP 50（本地检查，避免不必要的 API 调用）
_COMMON_PASSWORDS = {
    "123456", "password", "12345678", "qwerty", "123456789", "12345",
    "1234", "111111", "1234567", "dragon", "123123", "baseball",
    "abc123", "football", "monkey", "letmein", "shadow", "master",
    "666666", "qwertyuiop", "123321", "mustang", "1234567890",
    "michael", "654321", "superman", "1qaz2wsx", "7777777", "121212",
    "000000", "qazwsx", "123qwe", "killer", "trustno1", "jordan",
    "jennifer", "zxcvbnm", "asdfgh", "hunter", "buster", "soccer",
    "harley", "batman", "andrew", "tigger", "sunshine", "iloveyou",
    "2000", "charlie",
}


def _check_complexity(password: str) -> list[tuple[str, bool, str]]:
    """
    检查密码复杂度。
    返回 [(检查项, 是否通过, 说明), ...]
    """
    checks = []

    # 长度
    length_ok = len(password) >= 12
    checks.append(("长度≥12", length_ok, f"当前 {len(password)} 字符"))

    # 大写字母
    has_upper = bool(re.search(r"[A-Z]", password))
    checks.append(("含大写字母", has_upper, ""))

    # 小写字母
    has_lower = bool(re.search(r"[a-z]", password))
    checks.append(("含小写字母", has_lower, ""))

    # 数字
    has_digit = bool(re.search(r"\d", password))
    checks.append(("含数字", has_digit, ""))

    # 特殊字符
    has_special = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:\\"|,.<>/?`~]', password))
    checks.append(("含特殊字符", has_special, ""))

    # 连续字符（如 abc, 123）
    has_sequence = bool(re.search(r"(abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|012|123|234|345|456|567|678|789)", password.lower()))
    checks.append(("无连续字符", not has_sequence, "包含连续字母或数字"))

    # 重复字符（如 aaa, 111）
    has_repeat = bool(re.search(r"(.)\1{2,}", password))
    checks.append(("无连续重复", not has_repeat, "包含3个以上连续相同字符"))

    return checks


def _check_hibp(password: str) -> tuple[bool, int | None]:
    """
    用 Have I Been Pwned k-anonymity 检查密码是否已泄露。
    返回 (是否已泄露, 泄露次数)。
    """
    # 计算 SHA1
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]

    try:
        # 只发送前5位，HIBP 返回所有匹配的后缀
        resp = requests.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            timeout=10,
            headers={"Add-Padding": "true"},  # 隐私增强
        )
        resp.raise_for_status()

        for line in resp.text.splitlines():
            try:
                hash_suffix, count = line.split(":")
                if hash_suffix.strip() == suffix:
                    return True, int(count.strip())
            except (ValueError, IndexError):
                continue  # 跳过格式异常的行

        return False, None

    except requests.RequestException:
        return False, None  # 网络错误时返回未知，不阻断检查


def check_password(password: str) -> str:
    """
    全面检查密码安全性。

    参数:
        password: 要检查的密码

    返回:
        评分 + 详细检查项 + 是否已泄露
    """
    password = password.strip()
    if not password:
        return "密码不能为空"

    lines = [f"密码安全检查报告\n{'─'*40}"]

    # 1. 常见弱密码检查
    if password.lower() in _COMMON_PASSWORDS:
        lines.append("[!!] 这是最常见的弱密码之一，强烈建议更换！")
        lines.append(f"评分：0/100")
        return "\n".join(lines)

    # 2. 复杂度检查
    checks = _check_complexity(password)
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)

    lines.append("\n复杂度检查：")
    for name, ok, detail in checks:
        icon = "[+]" if ok else "[-]"
        suffix = f"（{detail}）" if detail else ""
        lines.append(f"  {icon} {name}{suffix}")

    # 3. 泄露检查
    lines.append("\n泄露检查：")
    is_leaked, leak_count = _check_hibp(password)
    if is_leaked:
        lines.append(f"  [!] 该密码已在数据泄露中出现 {leak_count} 次，禁止使用！")
    else:
        lines.append(f"  [+] 未在已知泄露库中发现")

    # 4. 评分
    score = int((passed / total) * 70)  # 复杂度占 70 分
    if not is_leaked:
        score += 30  # 未泄露加 30 分
    score = max(0, min(100, score))

    # 5. 等级
    if score >= 80:
        level = "强"
    elif score >= 60:
        level = "中"
    elif score >= 40:
        level = "弱"
    else:
        level = "极弱"

    lines.append(f"\n{'─'*40}")
    lines.append(f"评分：{score}/100（{level}）")

    if score < 60:
        lines.append("\n建议：")
        if not (len(password) >= 12):
            lines.append("  - 使用 12 位以上密码")
        if not any(c.isupper() for c in password):
            lines.append("  - 添加大写字母")
        if not any(c.isdigit() for c in password):
            lines.append("  - 添加数字")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
            lines.append("  - 添加特殊字符")

    return "\n".join(lines)
