#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置 X (Twitter) 账号 cookie —— 一键换号工具。

作用：把一份账号 cookie 上传到硅谷服务器，设成「搜索用」(search.json) 或
「发布用」(publish.json)。让"换成自己的账号来搜 / 发"变成一条命令。

cookie 是 twikit 格式：{"auth_token":"...","ct0":"..."}
搜索 (search.json) 和发布 (publish.json) 两个角色相互独立，可以用不同的号。

用法：
  # 从本机 Firefox 自动取当前登录的 X 号(浏览器先登录好你要用的号)
  python set_cookie.py --role search  --from-firefox
  python set_cookie.py --role publish --from-firefox

  # 手动填(给别人 / 给别的浏览器用)
  python set_cookie.py --role search  --auth-token <AT> --ct0 <CT0>
  python set_cookie.py --role publish --auth-token <AT> --ct0 <CT0>

参数：
  --role search|publish   设成搜索用 (search.json) 还是发布用 (publish.json)，必填
  --from-firefox          从本机 Firefox 自动读取当前登录 X 号的 cookie
  --auth-token <AT>       手动指定 auth_token(与 --ct0 一起用)
  --ct0 <CT0>             手动指定 ct0(与 --auth-token 一起用)

怎么从浏览器手动拿 auth_token / ct0：
  浏览器开发者工具(F12) → Application/存储 → Cookies → x.com → 复制 auth_token 和 ct0。

安全：服务器密码只从 .secrets/server.json 读，不打印密码、不打印 cookie 全值
      (只打印前 6 位 + 长度，便于核对)。
"""
import os
import sys
import glob
import json
import shutil
import sqlite3
import tempfile
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
SERVER_JSON = SKILL_ROOT / ".secrets" / "server.json"

# 服务器上的 cookie 目标路径(独立 X 工具箱 QuriovXTools)
REMOTE_COOKIE_DIR = r"C:\QuriovXTools\cookies"
REMOTE_COOKIE_PATH = {
    "search": r"C:\QuriovXTools\cookies\search.json",
    "publish": r"C:\QuriovXTools\cookies\publish.json",
}


def load_server_config() -> dict:
    if not SERVER_JSON.exists():
        print(
            f"[错误] 找不到服务器连接配置：{SERVER_JSON}\n"
            '请创建 .secrets/server.json，格式：\n'
            '{"host":"...","port":22,"user":"...","password":"..."}',
            file=sys.stderr,
        )
        sys.exit(2)
    with open(SERVER_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    for k in ("host", "port", "user", "password"):
        if k not in cfg:
            print(f"[错误] server.json 缺少字段：{k}", file=sys.stderr)
            sys.exit(2)
    return cfg


def find_firefox_cookie_db() -> str:
    """扫 Firefox 各 profile 的 cookies.sqlite，挑出含 x.com auth_token 的那个。"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("[错误] 找不到 %APPDATA% 环境变量，无法定位 Firefox 配置。", file=sys.stderr)
        sys.exit(2)
    pattern = os.path.join(appdata, "Mozilla", "Firefox", "Profiles", "*", "cookies.sqlite")
    candidates = glob.glob(pattern)
    if not candidates:
        print(
            "[错误] 没找到任何 Firefox cookies.sqlite。\n"
            f"已扫描：{pattern}\n"
            "请确认本机装了 Firefox 且已用它登录过 x.com，"
            "或改用手动方式：--auth-token <AT> --ct0 <CT0>。",
            file=sys.stderr,
        )
        sys.exit(2)

    # serial-ok: 仅本地少量 profile 文件探测，逐个找到含 x.com auth_token 的即停
    for db_path in candidates:
        creds = try_read_firefox_cookies(db_path)
        if creds.get("auth_token"):
            return db_path

    print(
        "[错误] 在 Firefox 的所有 profile 里都没找到 x.com 的 auth_token。\n"
        "请先用 Firefox 登录你要用的 X 号(确保是登录状态)，再重试；\n"
        "或改用手动方式：--auth-token <AT> --ct0 <CT0>。",
        file=sys.stderr,
    )
    sys.exit(2)


def try_read_firefox_cookies(db_path: str) -> dict:
    """复制 cookies.sqlite 到临时副本再读(避免 Firefox 占用锁)，读完删副本。"""
    tmp_dir = tempfile.mkdtemp(prefix="xcookie_")
    tmp_db = os.path.join(tmp_dir, "cookies.sqlite")
    creds = {"auth_token": None, "ct0": None}
    try:
        shutil.copy2(db_path, tmp_db)
        conn = sqlite3.connect(tmp_db)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name, value FROM moz_cookies "
                "WHERE host LIKE '%x.com%' AND name IN ('auth_token','ct0')"
            )
            for name, value in cur.fetchall():
                if name in creds:
                    creds[name] = value
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        # 单个 profile 读失败不致命，返回空让上层继续找下一个
        pass
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return creds


def get_cookie_from_firefox() -> dict:
    db_path = find_firefox_cookie_db()
    creds = try_read_firefox_cookies(db_path)
    if not creds.get("auth_token") or not creds.get("ct0"):
        print(
            "[错误] 从 Firefox 读到的 cookie 不完整(缺 auth_token 或 ct0)。\n"
            "请确认已在 Firefox 登录 x.com，或改用手动 --auth-token / --ct0。",
            file=sys.stderr,
        )
        sys.exit(2)
    return {"auth_token": creds["auth_token"], "ct0": creds["ct0"]}


def connect_ssh(cfg: dict) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=cfg["host"],
            port=int(cfg["port"]),
            username=cfg["user"],
            password=cfg["password"],
            timeout=30,
            banner_timeout=30,
            auth_timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )
        return client
    except Exception as e:  # noqa: BLE001
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
        print(f"[SSH 连接失败] {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


def mask(value: str) -> str:
    """只显示前 6 位 + 长度，绝不打印全值。"""
    if not value:
        return "(空)"
    return f"{value[:6]}…(共 {len(value)} 位)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="配置 X 账号 cookie：上传到服务器设成搜索用 / 发布用"
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=["search", "publish"],
        help="设成搜索用 (search.json) 还是发布用 (publish.json)",
    )
    parser.add_argument(
        "--from-firefox",
        action="store_true",
        help="从本机 Firefox 自动读取当前登录 X 号的 cookie",
    )
    parser.add_argument("--auth-token", dest="auth_token", default=None, help="手动指定 auth_token")
    parser.add_argument("--ct0", dest="ct0", default=None, help="手动指定 ct0")
    args = parser.parse_args()

    # 1. 取 cookie
    if args.from_firefox:
        if args.auth_token or args.ct0:
            print(
                "[错误] --from-firefox 不能和 --auth-token/--ct0 同时用，二选一。",
                file=sys.stderr,
            )
            return 2
        cookie = get_cookie_from_firefox()
    else:
        if not args.auth_token or not args.ct0:
            print(
                "[错误] 请二选一：\n"
                "  (a) --from-firefox  从 Firefox 自动取\n"
                "  (b) --auth-token <AT> --ct0 <CT0>  手动填(两个都要给)",
                file=sys.stderr,
            )
            return 2
        cookie = {"auth_token": args.auth_token, "ct0": args.ct0}

    # 2. 组成 twikit 格式 JSON
    payload = json.dumps({"auth_token": cookie["auth_token"], "ct0": cookie["ct0"]}, ensure_ascii=False)
    target = REMOTE_COOKIE_PATH[args.role]

    # 3. 连服务器，SFTP 上传
    cfg = load_server_config()
    ssh = connect_ssh(cfg)
    try:
        # 确保目标目录存在
        ssh.exec_command(f'if not exist "{REMOTE_COOKIE_DIR}" mkdir "{REMOTE_COOKIE_DIR}"')
        sftp = ssh.open_sftp()
        try:
            with sftp.open(target, "w") as rf:
                rf.write(payload)
        finally:
            sftp.close()
    finally:
        ssh.close()

    # 4. 确认(不打印全值)
    print(
        f"[成功] 已配置 {args.role} 角色的 cookie。\n"
        f"  目标路径：{target}\n"
        f"  auth_token：{mask(cookie['auth_token'])}\n"
        f"  ct0：       {mask(cookie['ct0'])}\n"
        f"  下次 {'搜索' if args.role == 'search' else '发布'} 将以这个账号身份进行。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
