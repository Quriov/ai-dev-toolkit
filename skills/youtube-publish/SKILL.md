---
name: youtube-publish
description: 往 YouTube 发评论 + 回复评论。用官方 YouTube Data API v3 的写操作（需 OAuth2 用户授权，和「读」只要 API key 不同：写要以你的 Google 账号身份授权一次）。当用户说"在 youtube 评论"、"发评论到 youtube"、"给这个 youtube 视频评论 xxx"、"在 youtube 视频下评论 xxx"、"回复这个 youtube 评论"、"在 youtube 视频下回复 xxx"、"给这条 youtube 评论回个 xxx"、"帮我在 youtube 发条评论"时触发本 skill。安全门：默认 dry-run（只验证 token、显示将发什么，不真发），必须显式加 --send 才真正发出。与 youtube-research（读）、x-publish（发）同属社媒 skill 家族：youtube-research 负责读、本 skill 负责写。
---

# YouTube 发评论 / 回复评论 Skill

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"在 youtube 评论"、"发评论到 youtube"、"帮我在 youtube 发条评论"
- 用户说"给这个 youtube 视频评论 xxx"、"在 youtube 视频下评论 xxx"
- 用户说"回复这个 youtube 评论"、"在 youtube 视频下回复 xxx"、"给这条 youtube 评论回个 xxx"

> ⚠️ **重要前提**：发出的评论是以**你授权的那个 Google 账号**身份发的。
> 动手前必须让用户知情并确认。

---

## 二、和 youtube-research（读）的区别：为什么要 OAuth 授权

| | youtube-research（读） | youtube-publish（本 skill，写） |
|---|---|---|
| 干啥 | 搜视频、读统计、读评论 | 发评论、回复评论 |
| 凭据 | 一个免费 **API key** 即可 | 需 **OAuth2 用户授权**（以你的账号身份） |
| 为什么 | 读公开数据不需要"是谁" | 写操作要知道"以谁的身份发"，必须本人授权 |

所以本 skill 多一道一次性授权（跑 `oauth_setup.py`），之后令牌自动续期、不用反复授权。

---

## 三、配置步骤（重点，给非技术用户一步步）

> 共三步：① 在 Google Cloud 建凭据下载 → ② 跑一次授权 → ③ 之后就能发。

### 第 1 步：在 Google Cloud 建「OAuth 客户端」并下载凭据

1. 打开 Google Cloud Console（读侧 youtube-research 已经启用过 YouTube Data API v3 的**同一个项目**即可，不用新建）。
2. 左侧菜单：「API 和服务」→「凭据」。
3. 顶部「创建凭据」→ 选「OAuth 客户端 ID」。
   - 如果第一次建会让你先配「OAuth 同意屏幕」：用户类型选「外部」，应用名随便填，
     **并把你自己的 Google 邮箱加进「测试用户」**（很重要，见第六节"已知坑"）。
4. 应用类型选「**桌面应用 (Desktop app)**」，名字随便起（如 `youtube-publish`）。
5. 创建后点「下载 JSON」。
6. 把下载的文件**改名为 `client_secret.json`**，放到本 skill 的 `.secrets\` 文件夹。

### 第 2 步：跑一次授权（生成令牌）

```
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
python scripts\oauth_setup.py
```

- 会自动弹出浏览器，让你用 Google 账号登录并点「允许」。
- 若提示「此应用未经验证」：点「高级」→「转至 …（不安全）」继续即可
  （因为是你自己建的、未提交 Google 审核的应用，正常现象，详见第六节）。
- 授权成功后，会自动生成 `.secrets\token.json`（含自动续期的 refresh_token）。

### 第 3 步：之后就能发评论了

授权完一次，后面直接用 `post_comment.py`（令牌过期会自动刷新，不用再授权）。

---

## 四、用法

### 发顶层评论

```
# 默认 dry-run：只验证 token 有效、显示将发什么，不真发
python scripts\post_comment.py comment --video VIDEO_ID --text "Great video!"

# 真正发出
python scripts\post_comment.py comment --video VIDEO_ID --text "Great video!" --send
```

> `VIDEO_ID` = 视频 URL `https://www.youtube.com/watch?v=VIDEO_ID` 里 `v=` 后面那串。

### 回复某条评论

```
# dry-run
python scripts\post_comment.py reply --parent COMMENT_ID --text "Thanks!"

# 真正发出
python scripts\post_comment.py reply --parent COMMENT_ID --text "Thanks!" --send
```

> `COMMENT_ID` = 要回复的那条评论的 ID（从 youtube-research 读评论时返回里能拿到）。

### 参数速查表

| 子命令 | 参数 | 说明 |
|--------|------|------|
| `comment` | `--video VIDEO_ID` | 目标视频 ID（必填） |
| `comment` | `--text TEXT` | 评论正文（必填） |
| `reply` | `--parent COMMENT_ID` | 要回复的评论 ID（必填） |
| `reply` | `--text TEXT` | 回复正文（必填） |
| 公共 | `--send` | **真正发出**；不加则只 dry-run 验证、不真发 |

> 🔒 **安全门（核心设计）**：**默认 dry-run**。不加 `--send` 时，脚本只做：加载令牌 →
> 调一个只读轻量接口（取你自己的频道）验证 token 有效 → 显示将要发的内容和模式，
> **绝不真发**。确认无误后再加 `--send`。

---

## 五、输出格式（JSON 打到 stdout，AI 直接读）

**dry-run 输出：**
```json
{"dry_run": true, "token_valid": true, "channel_title": "你的频道名",
 "mode": "comment", "would_post_text": "...", "posted": false, "video_id": "..."}
```

**--send 真发成功（发评论）：**
```json
{"posted": true, "mode": "comment", "id": "评论ID", "video_id": "...",
 "url": "https://www.youtube.com/watch?v=...&lc=评论ID"}
```

**--send 真发成功（回复）：**
```json
{"posted": true, "mode": "reply", "id": "回复ID", "parent_id": "...",
 "url": "https://www.youtube.com/comment?lc=回复ID"}
```

| 字段 | 含义 |
|------|------|
| `posted` | 是否真的发出（dry-run 恒为 false） |
| `dry_run` | 是否 dry-run 模式 |
| `token_valid` / `channel_title` | dry-run 校验项：令牌有效 + 你的频道名 |
| `mode` | `comment`（发评论） / `reply`（回复评论） |
| `would_post_text` | dry-run 下将要发的内容 |
| `id` / `url` | 真发后的评论/回复 ID 和链接 |

---

## 六、安全护栏（必读，按重要度排序）

| 护栏 | 说明 |
|------|------|
| **默认 dry-run** | 不加 `--send` 永远不真发。发前先 dry-run 确认文案、模式、token 正常。 |
| **发前用户确认** | 真发（`--send`）前必须把要发的完整内容给用户看、得到明确同意。评论是以你的 Google 账号身份发的，不可随意。 |
| **低频** | 高频发评论极易被 YouTube 判为垃圾、限制甚至封号。别批量刷、别短时间连发。 |
| **凭据安全** | `client_secret.json` / `token.json` 绝不进 git。`.secrets\` 已被 `.gitignore` 忽略；脚本只从 `.secrets\` 读，不打印凭据内容、不 hardcode 任何真实凭据。 |
| **账号归属知情** | 发的是**你授权的 Google 账号**，每次发前向用户讲清是哪个账号。 |

---

## 七、已知坑 / 风险（诚实写明，重要）

| 类别 | 说明 |
|------|------|
| **未验证应用只能给测试用户用** | Google 对 OAuth 写操作管控严：**未提交 Google 审核的应用**只能给「OAuth 同意屏幕」里「测试用户」名单中的账号授权。**把你自己的 Google 账号加进测试用户即可**。没加 → 授权时会被拒。 |
| **写操作耗配额多** | 评论写操作（`commentThreads.insert`）≈ **50 配额/次**（读评论才 1 配额）。每天 1 万配额 ≈ 约 200 次发评论封顶。别狂发。 |
| **平台可能拦截 API 评论** | YouTube 为防垃圾，可能把 API 发的评论**静默拦截 / 标记待审 / 不显示**。这是平台行为，不是脚本 bug。返回成功但评论不可见时，多半是这个。 |
| **令牌会过期/被撤销** | `token.json` 含 refresh_token 可自动续期；但若你在 Google 账号里手动撤销了授权、或长期不用，refresh_token 会失效。届时删掉 `.secrets\token.json` 重跑 `oauth_setup.py` 即可。 |
| **「未经验证」提示** | 自建未审核应用授权时浏览器会警告「此应用未经验证」，点「高级」→「继续」即可。这是正常的（你信任自己建的应用）。 |
| **合规** | API 自动发评论禁止用于垃圾营销、刷量、未授权推广等用途；违反会被封号且违反 YouTube ToS。 |

---

## 八、与同家族 skill 的关系

| Skill | 干啥 | 凭据 |
|-------|------|------|
| `youtube-research` | **读** YouTube：搜视频 / 读统计 / 读评论 | 免费 API key |
| **`youtube-publish`（本 skill）** | **写** YouTube：发评论 / 回复评论 | OAuth2 用户授权 |
| `x-publish` | **写** X（推特）：发推 / 回复 | 服务器 cookie |

YouTube 一读一写互为姊妹（research 读、publish 写）；x-publish 是另一平台的"发"侧姊妹，
安全门设计（默认 dry-run、`--send` 才真发）保持一致。

---

## 九、文件清单

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 本文档 |
| `scripts/oauth_setup.py` | **一次性授权**：弹浏览器走 OAuth2，生成 `.secrets/token.json` |
| `scripts/post_comment.py` | **主入口**：发评论 / 回复评论。默认 dry-run，`--send` 才真发 |
| `requirements.txt` | 依赖（google-api-python-client / google-auth-oauthlib / google-auth-httplib2） |
| `.gitignore` | 忽略 `.secrets/`、令牌、缓存等 |
| `.secrets/README.txt` | 说明要放哪两个凭据文件（client_secret.json + token.json） |
| `.secrets/client_secret.json` | OAuth 桌面应用凭据，**不进 git，需各自从 Google Cloud 下载** |
| `.secrets/token.json` | 授权后自动生成的令牌，**不进 git，跑 oauth_setup.py 生成** |

---

## 十、参考链接

1. **commentThreads.insert（发顶层评论）**：https://developers.google.com/youtube/v3/docs/commentThreads/insert
2. **comments.insert（回复评论）**：https://developers.google.com/youtube/v3/docs/comments/insert
3. **OAuth2 授权（已安装应用）**：https://developers.google.com/youtube/v3/guides/auth/installed-apps
4. **配额计算器**：https://developers.google.com/youtube/v3/determine_quota_cost
5. **OAuth 同意屏幕 / 测试用户**：https://support.google.com/cloud/answer/10311615
