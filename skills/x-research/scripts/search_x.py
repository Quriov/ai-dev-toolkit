#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按关键词搜索 X (Twitter) 推文 —— 编排器(orchestrator)。

架构：本机过不了 X 反爬，所以把搜索任务通过 SSH 发到美国硅谷服务器上跑
(那台服务器的 twikit 环境已验证能成功搜 X)，结果(JSON)传回本机 stdout。

逻辑：
  1. 从 .secrets/server.json 读服务器连接信息(不写死)。
  2. paramiko 连服务器(AutoAddPolicy, timeout 30; 握手失败退避重连 1 次)。
  3. SFTP 上传远程搜索脚本到服务器临时路径。
  4. 用服务器 venv 的 python 执行远程脚本，捕获 stdout。
  5. 删除远程临时脚本。
  6. 把远程脚本的 JSON 输出原样打到本机 stdout(给 AI 读)。
  7. 关连接。

用法：
  python search_x.py "smart glasses"
  python search_x.py "smart glasses" --count 30 --product Latest

参数：
  query              搜索关键词(位置参数，必填)
  --count N          返回推文条数(默认 20)
  --product MODE     Top(按热度) / Latest(默认，按时间) / Media(带图/视频)

安全：服务器密码只从 .secrets/server.json 读，不打印密码、不打印 cookie。
"""
import sys
import json
import time
import uuid
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
SERVER_JSON = SKILL_ROOT / ".secrets" / "server.json"

# 服务器上的固定路径(独立 X 工具箱 QuriovXTools，与 ai-infohub 分开)
REMOTE_PYTHON = r"C:\QuriovXTools\.venv\Scripts\python.exe"
REMOTE_COOKIES = r"C:\QuriovXTools\cookies\search.json"
REMOTE_TEMP_DIR = r"C:\Users\Administrator\AppData\Local\Temp"

# 远程搜索脚本(上传到服务器执行)。字段用 getattr 兜底，避免单字段缺失导致整脚本崩。
REMOTE_SCRIPT = r'''
import asyncio, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from twikit import Client

async def main():
    query = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    product = sys.argv[3] if len(sys.argv) > 3 else "Latest"
    client = Client(language="en-US")
    client.load_cookies(r"C:\QuriovXTools\cookies\search.json")
    tweets = await client.search_tweet(query, product)
    out = []
    for t in list(tweets)[:count]:
        user = getattr(t, "user", None)
        screen_name = getattr(user, "screen_name", None) if user else None
        out.append({
            "author": screen_name,
            "author_name": getattr(user, "name", None) if user else None,
            "text": getattr(t, "full_text", None) or getattr(t, "text", None),
            "likes": getattr(t, "favorite_count", None),
            "retweets": getattr(t, "retweet_count", None),
            "replies": getattr(t, "reply_count", None),
            "quotes": getattr(t, "quote_count", None),
            "views": getattr(t, "view_count", None),
            "created_at": str(getattr(t, "created_at", "")),
            "lang": getattr(t, "lang", None),
            "tweet_id": getattr(t, "id", None),
            "url": f"https://x.com/{screen_name}/status/{getattr(t, 'id', '')}" if screen_name else None,
        })
    print(json.dumps({"query": query, "count": len(out), "tweets": out}, ensure_ascii=False))

asyncio.run(main())
'''


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


def connect_ssh(cfg: dict) -> paramiko.SSHClient:
    """连服务器；握手失败退避重连 1 次(服务器对密集新连接有限流)。"""
    last_err = None
    # serial-ok: 退避重连，第 2 次依赖第 1 次失败结果，本质串行不可并发
    for attempt in range(2):
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
            last_err = e
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
            if attempt == 0:
                print(
                    f"[信息] SSH 握手失败，{type(e).__name__}，5 秒后退避重连一次…",
                    file=sys.stderr,
                )
                time.sleep(5)
    print(f"[SSH 连接失败] {type(last_err).__name__}: {last_err}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="搜索 X 推文(走硅谷服务器)")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--count", type=int, default=20, help="返回条数(默认 20)")
    parser.add_argument(
        "--product",
        choices=["Top", "Latest", "Media"],
        default="Latest",
        help="排序模式：Top / Latest(默认) / Media",
    )
    args = parser.parse_args()

    cfg = load_server_config()
    ssh = connect_ssh(cfg)

    remote_script_path = f"{REMOTE_TEMP_DIR}\\_xsearch_{uuid.uuid4().hex[:12]}.py"

    try:
        # 1. SFTP 上传远程脚本
        sftp = ssh.open_sftp()
        try:
            with sftp.open(remote_script_path, "w") as rf:
                rf.write(REMOTE_SCRIPT)
        finally:
            sftp.close()

        # 2. 执行远程脚本(参数用双引号包，防关键词含空格)
        cmd = (
            f'"{REMOTE_PYTHON}" "{remote_script_path}" '
            f'"{args.query}" {args.count} {args.product}'
        )
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        exit_code = stdout.channel.recv_exit_status()

        # 3. 删除远程临时脚本
        try:
            ssh.exec_command(f'del /f /q "{remote_script_path}"')
        except Exception:  # noqa: BLE001
            pass

        if exit_code != 0 or not out.strip():
            print(
                f"[远程执行失败] exit_code={exit_code}\n"
                f"--- 远程 stderr ---\n{err.strip()}",
                file=sys.stderr,
            )
            print(
                "[排查方向] (1) 服务器 venv/twikit 是否可用(C:\\QuriovXTools\\.venv) "
                "(2) cookie 是否过期(C:\\QuriovXTools\\cookies\\search.json) "
                "(3) X 风控。cookie 失效需重新提取并上传 search.json。",
                file=sys.stderr,
            )
            return 1

        # 4. 远程输出原样打到本机 stdout(它已是 JSON)
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")

        # 解析一下报条数(失败不影响主输出)
        try:
            data = json.loads(out.strip().splitlines()[-1])
            print(
                f"[信息] 共返回 {data.get('count')} 条推文 "
                f"(query={args.query!r}, product={args.product})",
                file=sys.stderr,
            )
        except Exception:  # noqa: BLE001
            pass
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
