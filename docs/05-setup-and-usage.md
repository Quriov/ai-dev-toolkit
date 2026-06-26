# 接手者上手指南

> 本篇说明：clone 这个仓库后，怎么让 6 个 skill 跑起来。
> 凭据、配置、常见问题都在这里。

---

## 第一步：安装 skill 到本地 Claude Code 环境

```bash
# 克隆仓库
git clone https://github.com/Quriov/ai-dev-toolkit.git
cd ai-dev-toolkit

# 运行安装脚本（把 skills/ 复制到 ~/.claude/skills/）
bash install.sh
```

安装完后，Claude Code 下次启动时会自动加载所有 skill，聊天里就能触发。

---

## 第二步：每个 Skill 的配置

### reddit-research — 无需配置，开箱即用

不需要任何账号或 key。AI 直接用 WebFetch 抓 Arctic Shift API，拿到数据后按 SKILL.md 的 SOP 提炼痛点。

**详细文档**：`skills/reddit-research/SKILL.md`

---

### youtube-research — 需要一个免费 API key

去 Google Cloud Console 申请（5 分钟，不绑卡）：
1. 打开 https://console.cloud.google.com/
2. 建或选一个项目
3. 启用 YouTube Data API v3
4. 创建凭据 → API 密钥 → 复制那串以 `AIzaSy` 开头的 key

拿到 key 后，AI 会在 WebFetch URL 里用你提供的 key 请求 YouTube 接口。key 不用写进文件，用时告诉 AI 即可（或存在一个安全的地方自己管理）。

**详细文档**：`skills/youtube-research/SKILL.md`

---

### x-research — 需要服务器连接信息 + 搜索账号 cookie

**准备工作**：

1. 创建 `.secrets/server.json`（把模板 `server.json.example` 复制过去，填入真实密码，密码找团队负责人要）：
   ```json
   {"host": "47.251.0.142", "port": 22, "user": "Administrator", "password": "服务器密码"}
   ```

2. 安装本机依赖（只需要 paramiko）：
   ```
   pip install -r skills/x-research/requirements.txt
   ```

3. 配置搜索账号 cookie（建议用小号，不要用品牌号）：
   ```
   cd skills/x-research
   python scripts/set_cookie.py --role search --from-firefox
   ```
   （先在 Firefox 登录好要用来搜索的 X 账号，再跑上面的命令）

> ⚠️ `.secrets/` 里的文件不进 git，每个人需要各自创建。

**详细文档**：`skills/x-research/SKILL.md`

---

### reddit-publish — 暂缓（等账号）

代码和文档已完成，但**真发功能未测通**。当前阻碍：账号用 Google 登录没有密码，PRAW 的 script 模式需要密码（详见踩坑台账坑 6）。

等账号问题解决后：
1. 在 Reddit 设置里添加独立密码（或注册新账号）
2. 去 https://www.reddit.com/prefs/apps 建 script 类型应用，拿 client_id / client_secret
3. 复制 `.secrets/reddit.json.example` 为 `.secrets/reddit.json`，填入真实值
4. 安装依赖：`pip install -r skills/reddit-publish/requirements.txt`

**详细文档**：`skills/reddit-publish/SKILL.md`

---

### youtube-publish — 需要 Google OAuth 授权（一次性）

**准备工作**：

1. 从团队负责人处拿到 `client_secret.json`（来自 Google Cloud 项目 `tidy-resolver-500509-j9`，应用名 `softskill`），放到 `skills/youtube-publish/.secrets/client_secret.json`。

2. 把你的 Google 账号邮箱加进 `tidy-resolver-500509-j9` 项目的"测试用户"名单（在 Google Cloud Console 的"OAuth 同意屏幕"设置里）。

3. 确保你的 Google 账号已创建 YouTube 频道（即使是空频道也行）。

4. 跑一次授权：
   ```
   cd skills/youtube-publish
   python scripts/oauth_setup.py
   ```
   浏览器会弹出授权窗口，登录并点"允许"，授权成功后自动生成 `.secrets/token.json`。

5. 之后就能用了（token 自动续期，不用反复授权）：
   ```
   python scripts/post_comment.py comment --video VIDEO_ID --text "内容" --send
   ```

**token 失效或换账号**：删掉 `.secrets/token.json`，重新跑 `python scripts/oauth_setup.py --force`。

**本工具无第三方依赖**，直接跑即可，不需要 `pip install`。

**详细文档**：`skills/youtube-publish/SKILL.md`

---

### x-publish — 需要服务器连接信息 + 发布账号 cookie

和 x-research 共用同一台服务器，但 cookie 独立。

**准备工作**：

1. 创建 `.secrets/server.json`（和 x-research 一样，找负责人要密码）。

2. 安装本机依赖：
   ```
   pip install -r skills/x-publish/requirements.txt
   ```

3. 配置发布账号 cookie：
   ```
   cd skills/x-publish
   python scripts/set_cookie.py --role publish --from-firefox
   ```
   （先在 Firefox 登录好要用来发推的 X 账号，当前是 @Quriov 品牌官号）

4. 发推（先 dry-run 确认，再加 `--send` 真发）：
   ```
   python scripts/post_x.py --text "内容" --send
   ```

> ⚠️ 发的是以你配的 cookie 账号（当前是品牌号 @Quriov）的身份发的，每次真发前必须让用户知情确认。

**详细文档**：`skills/x-publish/SKILL.md`

---

## 凭据放在哪儿

| Skill | 凭据文件位置（本地，不进 git） | 怎么获取 |
|-------|------------------------------|---------|
| x-research | `skills/x-research/.secrets/server.json` | 找团队负责人要服务器密码 |
| x-publish | `skills/x-publish/.secrets/server.json` | 同上 |
| youtube-publish | `skills/youtube-publish/.secrets/client_secret.json` | 找负责人拿，来自 Google Cloud `tidy-resolver-500509-j9` 项目 |
| youtube-publish | `skills/youtube-publish/.secrets/token.json` | 跑 `oauth_setup.py` 自动生成 |
| reddit-publish | `skills/reddit-publish/.secrets/reddit.json` | 自建 Reddit script 应用，模板见 `reddit.json.example` |

> **重要**：凭据不入库，各自在本地管理。找负责人要时，通过安全渠道（微信/飞书私聊，不通过 git / issue / 邮件）。

---

## 服务器工具箱（接手者参考）

X 两个 skill 依赖的服务器：
- **IP**：47.251.0.142
- **系统**：Windows Server 2025，管理员账号 Administrator
- **工具箱路径**：`C:\QuriovXTools\`（独立 venv + 打补丁 twikit + cookie 目录）
- **连接方式**：SSH 22 端口，密码找负责人要

服务器上 **不要动** `C:\AIInfoHub\`——那是自动日报管线，和这套工具无关。只操作 `C:\QuriovXTools\`。
