# 项目背景与目标 / 6 个 Skill 一览与状态

> 本篇说明：这个项目是什么、为什么做、做到了什么程度。
> 面向第一次接手的人，从背景读到现状，建立整体认知。

---

## 一、这个项目是什么

**一套"社媒读+发"工具**，让 AI 在和人聊天时，随口就能：
- **读**：搜 Reddit / YouTube / X 上的讨论、评论、推文，提炼用户痛点和口碑；
- **发**：往这三个平台发帖、发评论、发推文（或回复别人的内容）。

所有工具都做成了 **Claude Code skill** 的形式——每个 skill 是一个目录（`skills/<skill名>/`），里面放一份 `SKILL.md` 说明文档 + 配套的脚本（如果需要的话）。AI 加载 skill 后，就能按里面的 SOP 去干活。

**为什么放这个仓库（ai-dev-toolkit），不放眼镜业务仓库？**
这是通用工具，不属于任何一个具体业务项目。放工具库方便多个项目复用，也方便团队其他成员同步。

---

## 二、6 个 Skill 一览

| Skill 名 | 方向 | 平台 | 在 `skills/` 目录 |
|---------|------|------|------------------|
| `reddit-research` | 读 | Reddit | `skills/reddit-research/` |
| `youtube-research` | 读 | YouTube | `skills/youtube-research/` |
| `x-research` | 读 | X（推特） | `skills/x-research/` |
| `reddit-publish` | 发 | Reddit | `skills/reddit-publish/` |
| `youtube-publish` | 发 | YouTube | `skills/youtube-publish/` |
| `x-publish` | 发 | X（推特） | `skills/x-publish/` |

---

## 三、每个 Skill 的详细状态

### reddit-research — 读 Reddit

**做成了什么**
- 主路径：Arctic Shift API（免认证，直接用 AI 的 WebFetch 抓，不需要任何账号）。
- 备路径：reddit-mcp-buddy（需 OAuth）、Apify 付费方案、Academic Torrents 历史档案。
- 完整的痛点提取 SOP（第一版完整可用）。
- 来源引用格式规范（每条帖子/评论必须按格式引用）。

**实测情况**：Arctic Shift API 2026-06 实测可用，搜帖子、取评论树均正常返回真实数据。

**注意**：
- Arctic Shift 数据滞后约 36 小时，不适合实时事件监控。
- reddit-mcp-buddy 匿名模式 2026-06 实测不可用，必须配 OAuth。

---

### youtube-research — 读 YouTube

**做成了什么**
- 主路径：YouTube Data API v3（免费 key，每天 1 万配额，直接 WebFetch）。
- 三个端点：搜视频、读视频统计、读评论（高赞优先）。
- 无 key 兜底：oEmbed 端点（只能读单个视频的标题/作者）。
- 字幕降级方案（官方端点已失效，第三方转写可选）。
- 完整的痛点提取 SOP + 来源引用格式。

**实测情况**：用真实 API key 实测三个端点，全部返回真实数据，即刻可用。

**注意**：
- 需要用户自备一个免费 Google API key（不绑卡，去 Google Cloud Console 5 分钟搞定）。
- 官方字幕端点 2026 年被 POT token 堵死，字幕只能走第三方。

---

### x-research — 读 X（推特）

**做成了什么**
- 搜索脚本 `search_x.py`（SSH 编排器，把任务发到硅谷服务器执行）。
- 服务器架构：本机 paramiko SSH → 服务器 `C:\QuriovXTools\` 跑 twikit → JSON 回传。
- cookie 管理工具 `set_cookie.py`（换账号一条命令）。
- 完整的痛点提取 SOP + 推文引用格式。

**实测情况**：在服务器上验证 `search_tweet` 可用，能返回真实推文。端到端命令 `python scripts\search_x.py "smart glasses" --count 10` 成功返回 10 条真实推文。

**当前受限**：@Quriov 品牌官号被 X 临时限读（搜索接口返回 404，写接口仍正常）。根因是用品牌号高频搜索，被 X 自动限流。解法：用 `set_cookie.py --role search` 配一个搜索小号，或等限读自然恢复。

---

### reddit-publish — 发 Reddit

**做成了什么**
- 发帖脚本 `post_reddit.py`（PRAW 本机直连，支持发帖 / 回复帖子 / 回复评论）。
- 默认 dry-run 安全门（不加 `--send` 永不真发）。
- 凭据模板 `reddit.json.example`。

**实测情况**：`--help`、无凭据提示均正常。**真发未测**——当前账号用 Google 登录没有密码，PRAW 的 script 模式需要用户名+密码，所以卡在配置这一步。

**暂缓原因**：① Reddit 官方 API 有"Responsible Builder 政策"准入门槛，需审核；② 账号用 Google 登录没密码，PRAW 无法直接用。备选方案（用浏览器 Cookie 绕过密码）尚未实现。

---

### youtube-publish — 发 YouTube（评论）

**做成了什么**
- 授权脚本 `oauth_setup.py`（走 OAuth2，生成本地 token）。
- 发评论脚本 `post_comment.py`（发顶层评论 + 回复评论，纯 Python 标准库，无第三方依赖）。
- 默认 dry-run 安全门。

**实测情况**：实测真发一条评论到视频 + 立即删除，成功。账号：Siegfried（01babegjg@gmail.com）。

**重要**：授权相关的凭据（client_secret.json）在 Google Cloud 的 `tidy-resolver-500509-j9` 项目下，应用名 `softskill`。测试用户和 API 启用也在这个项目里——换账号或新人配置时要找这个项目。

---

### x-publish — 发 X（推特）

**做成了什么**
- 发推脚本 `post_x.py`（SSH 编排器，复用 x-research 的服务器路径）。
- 支持发新推 + 回复推文。
- 默认 dry-run 安全门（不加 `--send` 永不真发）。
- cookie 管理工具 `set_cookie.py`（与 x-research 共用，搜索/发布各用独立 cookie）。

**实测情况**：实测真发一条推到 @Quriov + 立即删除验证，成功。dry-run 已多次验证通过。

**发布账号**：当前由 `.secrets/server.json` + `C:\QuriovXTools\cookies\publish.json` 配置的账号（目前是 @Quriov 品牌官号）。注意：发的是品牌号，每次真发前必须让用户知情确认。
