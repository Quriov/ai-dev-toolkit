#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
往 YouTube 发评论 / 回复评论 —— 官方 YouTube Data API v3 写操作。

干什么：
  以你授权的 Google 账号身份，给某个 YouTube 视频发顶层评论，或回复某条已有评论。
  用官方 Data API v3 的 commentThreads.insert / comments.insert。

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
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

SKILL_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = SKILL_ROOT / ".secrets"
CLIENT_SECRET = SECRETS_DIR / "client_secret.json"
TOKEN_FILE = SECRETS_DIR / "token.json"


def _fail(msg: str, code: int = 1) -> int:
    print(msg, file=sys.stderr)
    return code


def load_credentials():
    """从 .secrets/token.json 加载凭据；过期则用 refresh_token 刷新并回存。

    返回 (creds, None) 成功；(None, 错误退出码) 失败（调用方据此返回）。
    """
    # 延迟 import，缺依赖时给清晰提示
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        return None, _fail(
            "[错误] 缺少依赖 google-auth / google-auth-oauthlib。请先安装：\n"
            "  pip install -r requirements.txt "
            "--trusted-host pypi.org --trusted-host files.pythonhosted.org",
            2,
        )

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
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    except Exception as e:  # noqa: BLE001
        return None, _fail(
            f"[错误] token.json 读取失败（可能损坏）：{type(e).__name__}: {e}\n"
            "请删掉 .secrets/token.json，重新跑 oauth_setup.py 授权。",
            2,
        )

    # 过期且有 refresh_token → 自动刷新并回存
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            print("[信息] 令牌已过期，已用 refresh_token 自动刷新并回存。", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            return None, _fail(
                f"[错误] 刷新令牌失败：{type(e).__name__}: {e}\n"
                "refresh_token 可能已失效（被撤销 / 过期）。\n"
                "请删掉 .secrets/token.json，重新跑 oauth_setup.py 授权。",
                1,
            )

    if not creds or not creds.valid:
        return None, _fail(
            "[错误] 令牌无效。请删掉 .secrets/token.json 重新跑 oauth_setup.py 授权。",
            1,
        )

    return creds, None


def build_youtube(creds):
    """用凭据建 YouTube Data API 服务。"""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        return None, _fail(
            "[错误] 缺少依赖 google-api-python-client。请先安装：\n"
            "  pip install -r requirements.txt "
            "--trusted-host pypi.org --trusted-host files.pythonhosted.org",
            2,
        )
    try:
        yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return yt, None
    except Exception as e:  # noqa: BLE001
        return None, _fail(f"[错误] 建立 YouTube 服务失败：{type(e).__name__}: {e}", 1)


def verify_token(youtube):
    """调一个只读轻量接口（取自己的频道）验证 token 有效。

    返回 (ok, channel_title, 错误信息)。
    """
    try:
        resp = youtube.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return True, None, None  # 授权有效但账号没有频道也算 token 可用
        title = items[0].get("snippet", {}).get("title")
        return True, title, None
    except Exception as e:  # noqa: BLE001
        return False, None, f"{type(e).__name__}: {e}"


def do_comment(youtube, video_id: str, text: str):
    """发顶层评论：commentThreads.insert。"""
    body = {
        "snippet": {
            "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": text}},
        }
    }
    resp = youtube.commentThreads().insert(part="snippet", body=body).execute()
    top = resp.get("snippet", {}).get("topLevelComment", {})
    cid = top.get("id", "")
    return {
        "posted": True,
        "mode": "comment",
        "id": cid,
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}&lc={cid}" if cid else None,
    }


def do_reply(youtube, parent_id: str, text: str):
    """回复某条评论：comments.insert。"""
    body = {"snippet": {"parentId": parent_id, "textOriginal": text}}
    resp = youtube.comments().insert(part="snippet", body=body).execute()
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
        description="往 YouTube 发评论/回复评论（官方 Data API v3；默认 dry-run，--send 才真发）"
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

    creds, err = load_credentials()
    if err is not None:
        return err

    youtube, err = build_youtube(creds)
    if err is not None:
        return err

    # 验证 token（dry-run 和真发都先验证一次）
    ok, channel_title, verr = verify_token(youtube)
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
            result = do_comment(youtube, args.video, args.text)
        else:
            result = do_reply(youtube, args.parent, args.text)
    except Exception as e:  # noqa: BLE001
        print(f"[发送失败] {type(e).__name__}: {e}", file=sys.stderr)
        print(
            "[排查方向] (1) 视频/评论 ID 是否正确、评论是否开放"
            " (2) 配额是否用尽（写操作耗配额较多）"
            " (3) 平台是否把 API 评论判为垃圾拦截。详见 SKILL.md「已知坑」。",
            file=sys.stderr,
        )
        return 1

    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    print(f"[成功] 已发出（{result.get('mode')}）：{result.get('url')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
