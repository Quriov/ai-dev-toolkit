#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YouTube 发评论 —— 一次性 OAuth2 授权。

干什么：
  用 Google 官方 OAuth2 流程，让你用自己的 Google 账号授权本工具「以你的身份发/回复
  YouTube 评论」。授权一次，生成 .secrets/token.json（含 refresh_token，可自动续期），
  之后 post_comment.py 就能复用，不用反复授权。

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
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 发评论/回复需要的写权限 scope
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

SKILL_ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = SKILL_ROOT / ".secrets"
CLIENT_SECRET = SECRETS_DIR / "client_secret.json"
TOKEN_FILE = SECRETS_DIR / "token.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="YouTube 发评论 OAuth2 一次性授权（生成 .secrets/token.json）"
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

    # 延迟 import，缺依赖时给清晰提示
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "[错误] 缺少依赖 google-auth-oauthlib。请先安装：\n"
            "  pip install -r requirements.txt "
            "--trusted-host pypi.org --trusted-host files.pythonhosted.org",
            file=sys.stderr,
        )
        return 2

    print(
        "[信息] 即将弹出浏览器，请用你的 Google 账号登录并授权。\n"
        "        （未验证的 OAuth 应用会提示「未经验证」，需把自己加进测试用户名单；\n"
        "         详见 SKILL.md「已知坑」。）",
        file=sys.stderr,
    )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=0)  # port=0 = 自动挑空闲端口
    except Exception as e:  # noqa: BLE001
        print(f"[授权失败] {type(e).__name__}: {e}", file=sys.stderr)
        print(
            "[排查方向] (1) client_secret.json 是否为「桌面应用」类型 "
            "(2) 是否把自己加进了 OAuth 测试用户 "
            "(3) 浏览器是否完成了授权点击。",
            file=sys.stderr,
        )
        return 1

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    print(f"[成功] 授权完成，令牌已保存到：{TOKEN_FILE}", file=sys.stderr)
    print(
        "[下一步] 现在可以用 post_comment.py 发评论了（默认 dry-run，--send 才真发）。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
