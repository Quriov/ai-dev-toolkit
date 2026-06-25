#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
【已废弃 / DEPRECATED — 2026-06-25】
本脚本是"本机用 twikit 直接登录 X 并导出 cookie"的旧路线。
经实测：本机(国内 IP)过不了 X 反爬，本机 twikit 路线确认不通，本脚本已无意义。

新架构：X 搜索改为通过 SSH 在硅谷服务器上执行(见 scripts/search_x.py)。
cookie 现在维护在服务器上 C:\\AIInfoHub\\data\\cookies.json，由 ai-infohub 维护，
不再由本脚本生成。保留此文件仅作历史记录，请勿使用。

----------------------------------------------------------------------
(以下为旧文档，仅供参考)

用 X (Twitter) 账号登录并导出 cookie。

凭据从环境变量读取（绝不 hardcode）：
  X_AUTH_INFO_1   邮箱或用户名（必填）
  X_AUTH_INFO_2   备用标识，X 登录有时会二次问用户名/手机号（可选）
  X_PASSWORD      密码（必填）
  X_TOTP_SECRET   两步验证 TOTP 密钥（可选，启用了 2FA 才需要）

cookie 导出到 .secrets/cookies.json（已被 .gitignore 忽略）。

用法（PowerShell）：
  $env:X_AUTH_INFO_1="你的邮箱"; $env:X_PASSWORD="你的密码"; python login_export_cookies.py

用法（bash）：
  X_AUTH_INFO_1="你的邮箱" X_PASSWORD="你的密码" python login_export_cookies.py

已知风险：login 可能触发 X 的验证（邮箱验证码 / 2FA / 可疑登录）。若卡在验证，
不要硬试——记录报错。建议用小号、低频、必要时挂海外/代理环境。
"""
import os
import sys
import asyncio
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from twikit import Client  # noqa: E402

# skill 根目录 = 本脚本上一级（scripts/ 的父目录）
SKILL_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = SKILL_ROOT / ".secrets"
COOKIES_PATH = SECRETS_DIR / "cookies.json"


async def main() -> int:
    auth_info_1 = os.environ.get("X_AUTH_INFO_1")
    auth_info_2 = os.environ.get("X_AUTH_INFO_2")  # 可选
    password = os.environ.get("X_PASSWORD")
    totp_secret = os.environ.get("X_TOTP_SECRET")  # 可选

    if not auth_info_1 or not password:
        print(
            "[错误] 缺少凭据。请设置环境变量 X_AUTH_INFO_1（邮箱/用户名）和 X_PASSWORD（密码）。",
            file=sys.stderr,
        )
        return 2

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    client = Client("en-US")
    print(f"[信息] 正在登录 X，账号：{auth_info_1[:3]}***", file=sys.stderr)

    try:
        await client.login(
            auth_info_1=auth_info_1,
            auth_info_2=auth_info_2,
            password=password,
            totp_secret=totp_secret,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[登录失败] {type(e).__name__}: {e}", file=sys.stderr)
        print(
            "[提示] 若提示需要验证码 / 2FA / 可疑登录，请勿硬试——"
            "改用小号、低频、必要时挂海外/代理环境，或人工在浏览器先登录一次。",
            file=sys.stderr,
        )
        return 1

    client.save_cookies(str(COOKIES_PATH))
    print(f"[成功] cookie 已导出到：{COOKIES_PATH}", file=sys.stderr)
    print(str(COOKIES_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
