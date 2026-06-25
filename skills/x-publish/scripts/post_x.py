#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
往 X (Twitter) 发推 / 回复推文 —— 编排器(orchestrator)。

架构：本机过不了 X 反爬，所以把发推/回复任务通过 SSH 发到美国硅谷服务器上跑
(那台服务器的 twikit 环境已验证能成功操作 X，与 x-research 同一台机、同一份 cookie)，
结果(JSON)传回本机 stdout。

⚠️ 发出的内容是以服务器那个 cookie 账号(ai-infohub)的身份发的。

安全门：默认 dry-run(只验证、不真发)，必须显式加 --send 才真正发推/回复。

逻辑：
  1. 从 .secrets/server.json 读服务器连接信息(不写死)。
  2. paramiko 连服务器(AutoAddPolicy, timeout 30; 握手失败退避重连 1 次)。
  3. dry-run：上传"只验证"的远程脚本——加载 cookie、确认 client 有 create_tweet 方法、
     打印将要发的文本和模式(发新推/回复)，但不调用 create_tweet。
  4. --send：上传远程脚本，真正调 create_tweet(...)，打印发出的推文 URL。
  5. 删除远程临时脚本。
  6. 把远程脚本的 JSON 输出原样打到本机 stdout(给 AI 读)。
  7. 关连接。

用法：
  python post_x.py --text "要发的内容"                         # 默认 dry-run，不真发
  python post_x.py --text "要发的内容" --send                  # 真正发新推
  python post_x.py --text "回复内容" --reply-to 1234567890      # dry-run 回复某推文
  python post_x.py --text "回复内容" --reply-to 1234567890 --send  # 真正回复

参数：
  --text TEXT        要发的推文/回复正文(必填)
  --reply-to ID      回复目标推文 ID(可选；不填=发新推，填=回复)
  --send             真正发出(不加则只 dry-run 验证，不真发)

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

# 服务器上的固定路径(由 ai-infohub 维护，与 x-research 同源)
REMOTE_PYTHON = r"C:\AIInfoHub\.venv\Scripts\python.exe"
REMOTE_COOKIES = r"C:\AIInfoHub\data\cookies.json"
REMOTE_TEMP_DIR = r"C:\Users\Administrator\AppData\Local\Temp"

# dry-run 远程脚本：只验证，绝不调用 create_tweet。
# argv[1]=text  argv[2]=reply_to(可能为空字符串)
REMOTE_SCRIPT_DRYRUN = r'''
import sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from twikit import Client

def main():
    text = sys.argv[1]
    reply_to = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    client = Client(language="en-US")
    client.load_cookies(r"C:\AIInfoHub\data\cookies.json")
    has_method = hasattr(client, "create_tweet")
    mode = "reply" if reply_to else "new_tweet"
    print(json.dumps({
        "dry_run": True,
        "cookie_loaded": True,
        "create_tweet_available": has_method,
        "mode": mode,
        "would_post_text": text,
        "reply_to": reply_to,
        "posted": False,
    }, ensure_ascii=False))

main()
'''

# --send 远程脚本：真正发推/回复。
# argv[1]=text  argv[2]=reply_to(可能为空字符串)
REMOTE_SCRIPT_SEND = r'''
import asyncio, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from twikit import Client

async def main():
    text = sys.argv[1]
    reply_to = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    client = Client(language="en-US")
    client.load_cookies(r"C:\AIInfoHub\data\cookies.json")
    kwargs = {"text": text}
    if reply_to:
        kwargs["reply_to"] = reply_to
    t = await client.create_tweet(**kwargs)
    tid = str(getattr(t, "id", ""))
    print(json.dumps({
        "posted": True,
        "mode": "reply" if reply_to else "new_tweet",
        "id": tid,
        "reply_to": reply_to,
        "url": f"https://x.com/i/status/{tid}",
    }, ensure_ascii=False))

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
    parser = argparse.ArgumentParser(
        description="往 X 发推/回复(走硅谷服务器；默认 dry-run，--send 才真发)"
    )
    parser.add_argument("--text", required=True, help="要发的推文/回复正文")
    parser.add_argument(
        "--reply-to",
        dest="reply_to",
        default=None,
        help="回复目标推文 ID(不填=发新推)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="真正发出(不加则只 dry-run 验证，不真发)",
    )
    args = parser.parse_args()

    if not args.text.strip():
        print("[错误] --text 不能为空", file=sys.stderr)
        return 2

    is_send = args.send
    remote_body = REMOTE_SCRIPT_SEND if is_send else REMOTE_SCRIPT_DRYRUN
    reply_to_arg = args.reply_to or ""

    if not is_send:
        print(
            "[安全门] 当前为 dry-run(只验证、不真发)。确认无误后加 --send 才会真正发出。",
            file=sys.stderr,
        )

    cfg = load_server_config()
    ssh = connect_ssh(cfg)

    remote_script_path = f"{REMOTE_TEMP_DIR}\\_xpublish_{uuid.uuid4().hex[:12]}.py"

    try:
        # 1. SFTP 上传远程脚本
        sftp = ssh.open_sftp()
        try:
            with sftp.open(remote_script_path, "w") as rf:
                rf.write(remote_body)
        finally:
            sftp.close()

        # 2. 执行远程脚本(text / reply_to 都用双引号包，防含空格)
        cmd = (
            f'"{REMOTE_PYTHON}" "{remote_script_path}" '
            f'"{args.text}" "{reply_to_arg}"'
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
                "[排查方向] (1) 服务器 venv/twikit 是否可用 "
                "(2) cookie 是否过期(C:\\AIInfoHub\\data\\cookies.json) "
                "(3) X 风控/发推被限。cookie 失效需在服务器上更新，由 ai-infohub 维护。",
                file=sys.stderr,
            )
            return 1

        # 4. 远程输出原样打到本机 stdout(它已是 JSON)
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")

        # 解析一下报状态(失败不影响主输出)
        try:
            data = json.loads(out.strip().splitlines()[-1])
            if data.get("posted"):
                print(
                    f"[成功] 已发出 ({data.get('mode')})：{data.get('url')}",
                    file=sys.stderr,
                )
            elif data.get("dry_run"):
                print(
                    f"[dry-run 通过] cookie 加载={data.get('cookie_loaded')}，"
                    f"create_tweet 方法存在={data.get('create_tweet_available')}，"
                    f"模式={data.get('mode')}。未真发。加 --send 才会真正发出。",
                    file=sys.stderr,
                )
        except Exception:  # noqa: BLE001
            pass
        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
