#!/usr/bin/env python3
"""
检查 MinerU Token 状态
读取 ~/.mineru/all_tokens.json，显示每个账户的 Token 过期时间和剩余天数。

退出码：
  0 = 所有 Token 有效
  1 = 存在过期 Token 或文件缺失
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加脚本目录到 path 以便 import _config
sys.path.insert(0, str(Path(__file__).parent))
from _config import TOKENS_FILE


def main():
    if not TOKENS_FILE.exists():
        print(f"Token 文件不存在: {TOKENS_FILE}")
        print("请先运行 batch_login.py 获取 Token")
        sys.exit(1)

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    if not tokens:
        print("Token 文件为空，请先运行 batch_login.py")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    expired_count = 0

    print(f"{'='*55}")
    print(f"  MinerU Token 状态")
    print(f"{'='*55}")

    for email, info in tokens.items():
        name = info.get("name", "")
        token_name = info.get("token_name", "")
        expired_at = info.get("expired_at", "")

        try:
            exp = datetime.fromisoformat(expired_at.replace("Z", "+00:00"))
            days = (exp - now).days
        except (ValueError, AttributeError):
            days = -1

        if days <= 0:
            status = "EXPIRED"
            expired_count += 1
        elif days <= 3:
            status = f"{days}d LEFT"
        else:
            status = f"{days}d OK"

        print(f"  {name:10s}  {email:30s}  {status}")

    print(f"{'='*55}")

    if expired_count > 0:
        print(f"  {expired_count} Token(s) EXPIRED - run batch_login.py")
        sys.exit(1)
    else:
        print(f"  ALL {len(tokens)} Token(s) VALID")
        sys.exit(0)


if __name__ == "__main__":
    main()
