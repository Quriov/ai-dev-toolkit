#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
往 YouTube 发评论 / 回复评论 —— 官方 YouTube Data API v3 写操作（纯标准库实现）。

干什么：
  以你授权的 Google 账号身份，给某个 YouTube 视频发顶层评论，或回复某条已有评论。
  调官方 Data API v3 的 commentThreads.insert / comments.insert。

为什么是纯标准库：
  本机 requests/urllib3（google-* 库底层用它）连 Google HTTPS 必崩
  （SSL: UNEXPECTED_EOF_WHILE_READING）。实测标准库 urllib.request 连 Google 正常，
  所以这里只用 urllib 跟 Google 通信，完全不碰 google-* / requests / httplib2。

前置：
  1. 先放 .secrets/client_secret.json（OAuth 桌面应用凭据，从 Google Cloud 下载）。
  2. 先跑一次 python scripts/oauth_setup.py 完成授权，生成 .secrets/token.json。
  （详见 SKILL.md「配置步骤」。）

安全门：默认 dry-run（只验证 token 有效、显示将要发什么，不真发）；必须显式加 --send 才真正发。

用法：
  # 发顶层评论 —— 默认 dry-run，只验证不真发
  python scripts/post_comment.py comment --video VIDEO_ID --text "..."
  # 发顶层评论 —— 真正发出
  python scripts/post_comment.py comment --video VIDEO_ID --text "..." --send

  # 回复某条评论 —— dry-run
  python scripts/post_comment.py reply --parent COMMENT_ID --text "..."
  # 回复某条评论 —— 真正发出
  python scripts/post_comment.py reply --parent COMMENT_ID --text "..." --send

参数：
  子命令 comment：--video VIDEO_ID（目标视频 ID）  --text TEXT（评论正文）
  子命令 reply  ：--parent COMMENT_ID（要回复的评论 ID）  --text TEXT（回复正文）
  公共：--send（真正发出；不加则只 dry-run 验证，不真发）

输出：JSON 打到 stdout（给 AI 读）。

安全：client_secret.json / token.json 只从 .secrets/ 读，不打印其内容、不进 git。
"""
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKEN_URI = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/youtube/v3"

SKILL_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = SKILL_ROOT / ".secrets"
TOKEN_FILE = SECRETS_DIR / "token.json"


def _fail(msg: str, code: int = 1) -> int:
    print(msg, file=sys.stderr)
    return code


def _refresh_token(tok: dict) -> dict:
    """用 urllib POST 刷新 access_token，回写 token.json，返回更新后的 dict。"""
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": tok["refresh_token"],
            "client_id": tok["client_id"],
            "client_secret": tok["client_secret"],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        tok.get("token_uri", TOKEN_URI),
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        new = json.load(resp)
    tok["access_token"] = new.get("access_token", tok.get("access_token"))
    tok["expiry_epoch"] = int(time.time()) + int(new.get("expires_in", 3600))
    if new.get("scope"):
        tok["scope"] = new["scope"]
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(tok, f, ensure_ascii=False, indent=2)
    return tok


def load_token():
    """从 .secrets/token.json 读令牌；过期（或快过期）则用 refresh_token 刷新并回存。

    返回 (tok_dict, None) 成功；(None, 错误退出码) 失败。
    """
    if not TOKEN_FILE.exists():
        return None, _fail(
            f"[错误] 找不到授权令牌：{TOKEN_FILE}\n"
            "你还没完成 OAuth 授权。请先：\n"
            "  1) 把 client_secret.json 放进 .secrets/（从 Google Cloud 下载的桌面应用凭据）\n"
            "  2) 跑：python scripts/oauth_setup.py（弹浏览器授权，生成 token.json）\n"
            "详细步骤见 SKILL.md「配置步骤」。",
            2,
        )

    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            tok = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return None, _fail(
            f"[错误] token.json 读取失败（可能损坏）：{type(e).__name__}: {e}\n"
            "请删掉 .secrets/token.json，重新跑 oauth_setup.py 授权。",
            2,
        )

    if not tok.get("access_token"):
        return None, _fail(
            "[错误] token.json 里没有 access_token。请重新跑 oauth_setup.py 授权。", 2
        )

    # 过期（留 60 秒余量）且有 refresh_token → 自动刷新
    expiry = int(tok.get("expiry_epoch", 0))
    if time.time() >= expiry - 60:
        if not tok.get("refresh_token"):
            return None, _fail(
                "[错误] access_token 已过期且没有 refresh_token，无法自动续期。\n"
                "请用 --force 重新跑 oauth_setup.py 授权（确保拿到 refresh_token）。",
                1,
            )
        try:
            tok = _refresh_token(tok)
            print("[信息] 令牌已过期，已用 refresh_token 自动刷新并回存。", file=sys.stderr)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return None, _fail(
                f"[错误] 刷新令牌失败：HTTP {e.code}：{body}\n"
                "refresh_token 可能已失效（被撤销 / 过期）。\n"
                "请删掉 .secrets/token.json，重新跑 oauth_setup.py 授权。",
                1,
            )
        except Exception as e:  # noqa: BLE001
            return None, _fail(
                f"[错误] 刷新令牌失败：{type(e).__name__}: {e}\n"
                "请删掉 .secrets/token.json，重新跑 oauth_setup.py 授权。",
                1,
            )

    return tok, None


def _api_request(method: str, url: str, access_token: str, body: dict = None):
    """用 urllib 调 YouTube Data API。返回解析后的 JSON。"""
    data = None
    headers = {"Authorization": f"Bearer {access_token}"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def verify_token(access_token: str):
    """调只读轻量接口（取自己的频道）验证 token 有效。

    返回 (ok, channel_title, 错误信息)。
    """
    url = f"{API_BASE}/channels?part=snippet&mine=true"
    try:
        resp = _api_request("GET", url, access_token)
        items = resp.get("items", [])
        if not items:
            return True, None, None  # 授权有效但账号没频道也算可用
        title = items[0].get("snippet", {}).get("title")
        return True, title, None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return False, None, f"HTTP {e.code}: {body}"
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"


def do_comment(access_token: str, video_id: str, text: str):
    """发顶层评论：commentThreads.insert。"""
    url = f"{API_BASE}/commentThreads?part=snippet"
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    resp = _api_request("POST", url, access_token, body)
    top = resp.get("snippet", {}).get("topLevelComment", {})
    cid = top.get("id", "")
    return {
        "posted": True,
        "mode": "comment",
        "id": cid,
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}&lc={cid}" if cid else None,
    }


def do_reply(access_token: str, parent_id: str, text: str):
    """回复某条评论：comments.insert。"""
    url = f"{API_BASE}/comments?part=snippet"
    body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
    resp = _api_request("POST", url, access_token, body)
    cid = resp.get("id", "")
    return {
        "posted": True,
        "mode": "reply",
        "id": cid,
        "parent_id": parent_id,
        "url": f"https://www.youtube.com/comment?lc={cid}" if cid else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="往 YouTube 发评论/回复评论（官方 Data API v3，纯标准库；默认 dry-run，--send 才真发）"
    )
    sub = parser.add_subparsers(dest="action", required=True)

    p_comment = sub.add_parser("comment", help="给某视频发顶层评论")
    p_comment.add_argument("--video", required=True, help="目标视频 ID（URL 里 v= 后面那串）")
    p_comment.add_argument("--text", required=True, help="评论正文")
    p_comment.add_argument(
        "--send", action="store_true", help="真正发出（不加则只 dry-run 验证，不真发）"
    )

    p_reply = sub.add_parser("reply", help="回复某条已有评论")
    p_reply.add_argument("--parent", required=True, help="要回复的评论 ID")
    p_reply.add_argument("--text", required=True, help="回复正文")
    p_reply.add_argument(
        "--send", action="store_true", help="真正发出（不加则只 dry-run 验证，不真发）"
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.text.strip():
        return _fail("[错误] --text 不能为空", 2)

    is_send = args.send
    if not is_send:
        print(
            "[安全门] 当前为 dry-run（只验证、不真发）。确认无误后加 --send 才会真正发出。",
            file=sys.stderr,
        )

    tok, err = load_token()
    if err is not None:
        return err

    access_token = tok["access_token"]

    # 验证 token（dry-run 和真发都先验证一次）
    ok, channel_title, verr = verify_token(access_token)
    if not ok:
        print(
            f"[错误] token 验证失败：{verr}\n"
            "[排查方向] (1) token.json 是否有效（重跑 oauth_setup.py）"
            " (2) 是否启用了 YouTube Data API v3"
            " (3) 配额是否用尽。",
            file=sys.stderr,
        )
        return 1

    mode = "comment" if args.action == "comment" else "reply"
    target = (
        {"video_id": args.video} if mode == "comment" else {"parent_id": args.parent}
    )

    if not is_send:
        out = {
            "dry_run": True,
            "token_valid": True,
            "channel_title": channel_title,
            "mode": mode,
            "would_post_text": args.text,
            "posted": False,
        }
        out.update(target)
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        print(
            f"[dry-run 通过] token 有效（频道：{channel_title}），模式={mode}。"
            "未真发。加 --send 才会真正发出。",
            file=sys.stderr,
        )
        return 0

    # 真发
    try:
        if mode == "comment":
            result = do_comment(access_token, args.video, args.text)
        else:
            result = do_reply(access_token, args.parent, args.text)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[发送失败] HTTP {e.code}：{body}", file=sys.stderr)
        print(
            "[排查方向] (1) 视频/评论 ID 是否正确、评论是否开放"
            " (2) 配额是否用尽（写操作耗配额较多）"
            " (3) 平台是否把 API 评论判为垃圾拦截。详见 SKILL.md「已知坑」。",
            file=sys.stderr,
        )
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[发送失败] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"[成功] 已发出（{result.get('mode')}）：{result.get('url')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
