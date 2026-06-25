#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
post_reddit.py — 往 Reddit 发帖 / 回复帖子 / 回复评论。

用 PRAW 库本机直接操作 Reddit。默认 dry-run（只验证登录、显示将要发什么，不真发），
必须显式加 --send 才真正发出。

凭据从同目录上一级的 .secrets/reddit.json 读取，格式见 .secrets/reddit.json.example。
源码不写死任何真实凭据；脚本不打印密码。

三种操作（子命令）：
  submit        — 发帖（self post，可选 --url 发链接帖）
  reply-post    — 回复某个帖子
  reply-comment — 回复某条评论

示例：
  python scripts/post_reddit.py submit --subreddit test --title "标题" --text "正文"
  python scripts/post_reddit.py submit --subreddit test --title "标题" --text "正文" --send
  python scripts/post_reddit.py submit --subreddit test --title "标题" --url https://example.com --send
  python scripts/post_reddit.py reply-post --post 1abcdef --text "回复内容" --send
  python scripts/post_reddit.py reply-comment --comment dq1abc2 --text "回复内容" --send
"""

import argparse
import json
import os
import sys

# 中文/emoji 输出不崩
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# .secrets/reddit.json 相对脚本位置：scripts/ 的上一级目录里的 .secrets/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SECRETS_PATH = os.path.join(SCRIPT_DIR, os.pardir, ".secrets", "reddit.json")
REQUIRED_KEYS = ["client_id", "client_secret", "username", "password", "user_agent"]


def out(obj):
    """统一把结果 JSON 打到 stdout，供 AI 直接读。"""
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def fail(msg, code=1, **extra):
    payload = {"ok": False, "error": msg}
    payload.update(extra)
    out(payload)
    sys.exit(code)


def load_credentials():
    """读取并校验 .secrets/reddit.json；缺文件/缺字段时给清晰提示并非 0 退出。"""
    if not os.path.exists(SECRETS_PATH):
        fail(
            "未找到凭据文件。请按 SKILL.md「配置步骤」创建 "
            ".secrets/reddit.json（可复制 .secrets/reddit.json.example 改写）。",
            code=2,
            expected_path=os.path.normpath(SECRETS_PATH),
        )
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
    except Exception as e:
        fail(f"凭据文件不是合法 JSON：{e}。请参考 .secrets/reddit.json.example。", code=2)

    missing = [k for k in REQUIRED_KEYS if not creds.get(k)]
    if missing:
        fail(
            "凭据文件缺少字段：" + ", ".join(missing)
            + "。请补全后重试（参考 .secrets/reddit.json.example）。",
            code=2,
        )
    return creds


def build_reddit(creds):
    """用凭据构建 PRAW Reddit 实例。"""
    try:
        import praw
    except ImportError:
        fail(
            "未安装 praw。请先运行："
            "pip install praw --trusted-host pypi.org --trusted-host files.pythonhosted.org",
            code=3,
        )
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        username=creds["username"],
        password=creds["password"],
        user_agent=creds["user_agent"],
    )


def verify_login(reddit):
    """验证凭据能登录，返回用户名。失败给清晰提示。"""
    try:
        me = reddit.user.me()
    except Exception as e:
        fail(
            f"登录验证失败：{e}。请检查 client_id/client_secret/用户名/密码是否正确，"
            "以及该应用是否为 script 类型（详见 SKILL.md）。",
            code=4,
        )
    if me is None:
        fail("登录验证失败：reddit.user.me() 返回空，凭据可能无效。", code=4)
    return str(me)


def cmd_submit(reddit, args, dry_run):
    """发帖。可选 --url 发链接帖；否则发 self post（正文）。"""
    is_link = bool(args.url)
    if not is_link and not args.text:
        fail("发 self 帖需要 --text 正文；发链接帖请用 --url。", code=5)

    plan = {
        "operation": "submit",
        "subreddit": args.subreddit,
        "title": args.title,
        "kind": "link" if is_link else "self",
    }
    if is_link:
        plan["url"] = args.url
    else:
        plan["text"] = args.text

    me = verify_login(reddit)
    plan["as_user"] = me

    if dry_run:
        plan.update({"dry_run": True, "posted": False})
        out({"ok": True, **plan})
        return

    try:
        sub = reddit.subreddit(args.subreddit)
        if is_link:
            submission = sub.submit(title=args.title, url=args.url)
        else:
            submission = sub.submit(title=args.title, selftext=args.text or "")
    except Exception as e:
        fail(f"发帖失败：{e}。常见原因：subreddit 发帖门槛（karma/账号年龄/规则）、被反垃圾过滤拦截。",
             code=6)

    out({
        "ok": True,
        "operation": "submit",
        "posted": True,
        "as_user": me,
        "id": submission.id,
        "url": "https://www.reddit.com" + submission.permalink,
    })


def cmd_reply_post(reddit, args, dry_run):
    """回复一个帖子。--post 可填帖子 id 或完整 url。"""
    me = verify_login(reddit)
    target = args.post

    plan = {
        "operation": "reply-post",
        "post": target,
        "text": args.text,
        "as_user": me,
    }
    if dry_run:
        plan.update({"dry_run": True, "posted": False})
        out({"ok": True, **plan})
        return

    try:
        if target.startswith("http://") or target.startswith("https://"):
            submission = reddit.submission(url=target)
        else:
            submission = reddit.submission(id=target)
        comment = submission.reply(args.text)
    except Exception as e:
        fail(f"回复帖子失败：{e}。可能：帖子已锁/已删、被反垃圾过滤拦截、账号受限。", code=6)

    out({
        "ok": True,
        "operation": "reply-post",
        "posted": True,
        "as_user": me,
        "id": comment.id,
        "url": "https://www.reddit.com" + comment.permalink,
    })


def cmd_reply_comment(reddit, args, dry_run):
    """回复一条评论。--comment 填评论 id。"""
    me = verify_login(reddit)

    plan = {
        "operation": "reply-comment",
        "comment": args.comment,
        "text": args.text,
        "as_user": me,
    }
    if dry_run:
        plan.update({"dry_run": True, "posted": False})
        out({"ok": True, **plan})
        return

    try:
        parent = reddit.comment(id=args.comment)
        comment = parent.reply(args.text)
    except Exception as e:
        fail(f"回复评论失败：{e}。可能：评论已删、帖子已锁、被反垃圾过滤拦截、账号受限。", code=6)

    out({
        "ok": True,
        "operation": "reply-comment",
        "posted": True,
        "as_user": me,
        "id": comment.id,
        "url": "https://www.reddit.com" + comment.permalink,
    })


def build_parser():
    p = argparse.ArgumentParser(
        description="往 Reddit 发帖 / 回复帖子 / 回复评论（默认 dry-run，--send 才真发）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", required=True)

    # submit
    sp = sub.add_parser("submit", help="发帖（self post，可选 --url 发链接帖）")
    sp.add_argument("--subreddit", required=True, help="目标 subreddit 名（不含 r/）")
    sp.add_argument("--title", required=True, help="帖子标题")
    sp.add_argument("--text", help="self 帖正文（不发链接帖时使用）")
    sp.add_argument("--url", help="发链接帖时的目标链接（填了即发链接帖）")
    sp.add_argument("--send", action="store_true", help="真正发出；不加则只 dry-run 验证")

    # reply-post
    rp = sub.add_parser("reply-post", help="回复某个帖子")
    rp.add_argument("--post", required=True, help="帖子 id 或完整 url")
    rp.add_argument("--text", required=True, help="回复内容")
    rp.add_argument("--send", action="store_true", help="真正发出；不加则只 dry-run 验证")

    # reply-comment
    rc = sub.add_parser("reply-comment", help="回复某条评论")
    rc.add_argument("--comment", required=True, help="评论 id")
    rc.add_argument("--text", required=True, help="回复内容")
    rc.add_argument("--send", action="store_true", help="真正发出；不加则只 dry-run 验证")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    dry_run = not args.send

    creds = load_credentials()
    reddit = build_reddit(creds)

    if args.command == "submit":
        cmd_submit(reddit, args, dry_run)
    elif args.command == "reply-post":
        cmd_reply_post(reddit, args, dry_run)
    elif args.command == "reply-comment":
        cmd_reply_comment(reddit, args, dry_run)
    else:
        parser.error("未知子命令")


if __name__ == "__main__":
    main()
