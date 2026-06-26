#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YouTube 发评论 —— 一次性 OAuth2 授权（纯标准库实现）。

干什么：
  用 Google 官方 OAuth2 流程，让你用自己的 Google 账号授权本工具「以你的身份发/回复
  YouTube 评论」。授权一次，生成 .secrets/token.json（含 refresh_token，可自动续期），
  之后 post_comment.py 就能复用，不用反复授权。

为什么是纯标准库：
  本机的 requests/urllib3（google-* 库底层用它）连 Google HTTPS 必崩
  （SSL: UNEXPECTED_EOF_WHILE_READING）。实测 Python 标准库 urllib.request 连 Google 正常，
  所以这里只用标准库（urllib / http.server）跟 Google 通信，完全不碰 google-* / requests。

前置：
  - 先把从 Google Cloud 下载的 OAuth 桌面应用凭据放到 .secrets/client_secret.json
    （怎么拿见 .secrets/README.txt 和 SKILL.md 的「配置步骤」）。

用法：
  python scripts/oauth_setup.py           # 弹浏览器走授权，生成 .secrets/token.json
  python scripts/oauth_setup.py --force    # 即使已有 token.json 也重新授权（覆盖）

安全：
  client_secret.json / token.json 只在 .secrets/（被 .gitignore 挡住），不打印其内容、不进 git。
"""
import sys
import json
import time
import socket
import argparse
import webbrowser
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 发评论/回复需要的写权限 scope
SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"

SKILL_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = SKILL_ROOT / ".secrets"
CLIENT_SECRET = SECRETS_DIR / "client_secret.json"
TOKEN_FILE = SECRETS_DIR / "token.json"


def _pick_free_port(preferred: int = 8765) -> int:
    """优先用 preferred 端口，被占用则让系统分配一个空闲端口。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
    finally:
        s.close()


class _CallbackHandler(BaseHTTPRequestHandler):
    """一次性本地回调处理器：抓 URL query 里的 code（纯本地，不碰 Google）。"""

    captured = {}

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _CallbackHandler.captured = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if "code" in _CallbackHandler.captured:
            msg = "授权完成，可以关闭此页面，回到命令行。"
        else:
            err = _CallbackHandler.captured.get("error", "未知错误")
            msg = f"授权失败：{err}。可关闭此页面，回到命令行查看提示。"
        self.wfile.write(
            f"<html><body style='font-family:sans-serif;font-size:18px;'>"
            f"{msg}</body></html>".encode("utf-8")
        )

    def log_message(self, *args):  # 静音 http.server 默认日志
        return


def _capture_code(port: int):
    """起一次性本地服务，接住一次回调请求后立即返回抓到的参数。"""
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    try:
        server.handle_request()  # 只处理一次请求
    finally:
        server.server_close()
    return _CallbackHandler.captured


def _exchange_code(client_id, client_secret, code, redirect_uri):
    """用 urllib POST 把授权码换成令牌。"""
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URI,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube 发评论 OAuth2 一次性授权（生成 .secrets/token.json，纯标准库）"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使已有 token.json 也强制重新授权（覆盖旧的）",
    )
    args = parser.parse_args()

    if not CLIENT_SECRET.exists():
        print(
            f"[错误] 找不到 OAuth 客户端凭据：{CLIENT_SECRET}\n"
            "请先去 Google Cloud Console 创建「OAuth 客户端 ID（桌面应用）」，\n"
            "下载 JSON 改名为 client_secret.json 放到 .secrets/。\n"
            "详细步骤见 SKILL.md「配置步骤」或 .secrets/README.txt。",
            file=sys.stderr,
        )
        return 2

    if TOKEN_FILE.exists() and not args.force:
        print(
            f"[信息] 已存在 token.json：{TOKEN_FILE}\n"
            "看起来你已经授权过了，直接用 post_comment.py 即可。\n"
            "若要重新授权（换账号 / token 失效），加 --force。",
            file=sys.stderr,
        )
        return 0

    # 读取客户端凭据（client_secret.json 形如 {"installed": {...}}）
    try:
        with open(CLIENT_SECRET, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        node = cfg.get("installed") or cfg.get("web") or {}
        client_id = node["client_id"]
        client_secret = node["client_secret"]
    except (KeyError, json.JSONDecodeError, OSError) as e:
        print(
            f"[错误] client_secret.json 读取/解析失败：{type(e).__name__}: {e}\n"
            "请确认它是从 Google Cloud 下载的「桌面应用」OAuth 凭据"
            "（顶层有 installed.client_id / client_secret）。",
            file=sys.stderr,
        )
        return 2

    port = _pick_free_port()
    redirect_uri = f"http://localhost:{port}"

    auth_url = AUTH_URI + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",  # 强制每次返回 refresh_token
        }
    )

    print(
        "[信息] 即将弹出浏览器，请用你的 Google 账号登录并授权。\n"
        "        （未验证的 OAuth 应用会提示「未经验证」，需把自己加进测试用户名单；\n"
        "         详见 SKILL.md「已知坑」。）\n"
        "        若浏览器没弹出，请手动复制下面这条链接到浏览器打开：\n"
        f"        {auth_url}",
        file=sys.stderr,
    )

    try:
        webbrowser.open(auth_url)
    except Exception:  # noqa: BLE001
        pass  # 弹不出来没关系，上面已打印链接

    print(f"[等待] 正在本地 {redirect_uri} 等待 Google 授权回调……", file=sys.stderr)
    try:
        captured = _capture_code(port)
    except Exception as e:  # noqa: BLE001
        print(f"[授权失败] 本地回调服务出错：{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if "error" in captured:
        print(f"[授权失败] Google 返回错误：{captured.get('error')}", file=sys.stderr)
        return 1
    code = captured.get("code")
    if not code:
        print("[授权失败] 没拿到授权码（可能用户取消了授权）。", file=sys.stderr)
        return 1

    # 用 urllib 换令牌
    try:
        tok = _exchange_code(client_id, client_secret, code, redirect_uri)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(
            f"[换令牌失败] HTTP {e.code}：{body}\n"
            "[排查方向] (1) client_secret 是否正确 "
            "(2) redirect_uri 是否被列入凭据允许列表（桌面应用通常不限制）。",
            file=sys.stderr,
        )
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[换令牌失败] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if "refresh_token" not in tok:
        print(
            "[警告] Google 没返回 refresh_token（可能此账号之前已授权过、未带 prompt=consent）。\n"
            "        建议用 --force 重新授权，确保拿到 refresh_token 以便自动续期。",
            file=sys.stderr,
        )

    token_data = {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "client_id": client_id,
        "client_secret": client_secret,
        "token_uri": TOKEN_URI,
        "scope": tok.get("scope", SCOPE),
        "expiry_epoch": int(time.time()) + int(tok.get("expires_in", 3600)),
    }

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)

    print(f"[成功] 授权完成，令牌已保存到：{TOKEN_FILE}", file=sys.stderr)
    print(
        "[下一步] 现在可以用 post_comment.py 发评论了（默认 dry-run，--send 才真发）。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
