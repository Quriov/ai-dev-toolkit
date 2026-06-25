---
name: reddit-publish
description: 往 Reddit 发帖 + 回复帖子/评论。用 PRAW 库本机直接跑（Reddit 没有像 X 那样的反爬封锁，本机可直连）。当用户说"发到 reddit"、"在 r/xxx 发帖"、"帮我发个 reddit 帖"、"发条 reddit"、"reddit 发个 xxx"、"回复这个 reddit 帖子"、"回复这条 reddit 评论"、"在 reddit 回复 xxx"、"给这个 reddit 帖子回个 xxx"时触发本 skill。安全门：默认 dry-run（只验证登录、显示将要发什么，不真发），必须显式加 --send 才真正发出。凭据放 .secrets/reddit.json（不进 git）。与 reddit-research（读）同属 Reddit skill 家族（那个负责搜/分析，这个负责发/回复）。
---

# Reddit 发帖 / 回复 Skill

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"发到 reddit"、"发条 reddit"、"reddit 发个 xxx"
- 用户说"在 r/xxx 发帖"、"帮我发个 reddit 帖 xxx"
- 用户说"回复这个 reddit 帖子"、"给这个帖子回个 xxx"
- 用户说"回复这条 reddit 评论"、"在 reddit 回复 xxx"

> ⚠️ **重要前提**：发出的内容是以 `.secrets/reddit.json` 里那个 Reddit 账号的身份发的。
> 真发（`--send`）前必须把要发的完整内容给用户看、得到明确同意。

---

## 二、架构：本机直接跑（和 X 不一样）

```
本机(post_reddit.py)
   │  ① 读 .secrets/reddit.json 拿账号凭据
   │  ② 用 PRAW 直连 Reddit 官方 API（本机国内 IP 也能连）
   │  ③ 默认 dry-run：验证登录 + 显示将发什么，不真发
   │     加 --send 才真正发帖/回复
   ▼
Reddit ④ 成功返回新帖/新评论的 permalink URL
```

**为什么不像 x-publish 那样走服务器？** Reddit 有官方 API，PRAW 是官方推荐的 Python 库，
本机直连就行，**没有 X 那种反爬封锁**。所以本 skill 直接在本机跑，结构比 x-publish 简单。

---

## 三、配置步骤（重点，给非技术用户）

只需做一次：

### 第 1 步：准备一个 Reddit 账号
注册或用现成的 Reddit 账号。新号有发帖门槛（见第六节风险），建议养一养再发。

### 第 2 步：创建一个 script 类型应用，拿 client_id / client_secret
1. 登录 Reddit，打开 https://www.reddit.com/prefs/apps
2. 拉到底，点 **"create another app..."**（创建应用）
3. 填写：
   - **name**：随便起，如 `quriov-publisher`
   - 类型选 **script**（脚本，重要！必须选这个）
   - **redirect uri**：填 `http://localhost:8080`（脚本模式用不上，但必须填一个）
4. 点 **create app**
5. 创建后：
   - **client_id** = 应用名称**下方**那一串字符（在 "personal use script" 字样旁边/下面）
   - **client_secret** = 标着 **secret** 的那一串

### 第 3 步：把凭据填进 .secrets/reddit.json
1. 复制 skill 根目录的 `reddit.json.example` 为 `.secrets/reddit.json`
2. 把占位值改成真实值：

```json
{
  "client_id": "上一步拿到的 client_id",
  "client_secret": "上一步拿到的 client_secret",
  "username": "你的 Reddit 用户名",
  "password": "你的 Reddit 密码",
  "user_agent": "script:com.quriov.reddit-publish:v1.0 (by /u/你的用户名)"
}
```

> ⚠️ `.secrets/` 已被 `.gitignore` 忽略，**不进 git、不会同步给团队其他人**。
> 团队其他成员要用，**各自手动创建这个文件**（凭据找负责人要）。
> `user_agent` 建议按上面格式写清楚（Reddit 要求标明用途和作者，乱写易被限制）。

### 第 4 步：装依赖
```
pip install -r requirements.txt
# 或： pip install praw --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

---

## 四、用法（三种操作）

> 🔒 **安全门（核心设计）**：**默认 dry-run**。不加 `--send` 时，脚本只验证「能登录、
> 显示将要发什么」，**绝不真发**。确认无误后再加 `--send`。

### 1. 发帖（submit）

```
# 发 self 帖（正文帖）—— dry-run，只验证不真发
python scripts/post_reddit.py submit --subreddit test --title "标题" --text "正文内容"

# 真正发出
python scripts/post_reddit.py submit --subreddit test --title "标题" --text "正文内容" --send

# 发链接帖（填 --url，不要 --text）—— 真发
python scripts/post_reddit.py submit --subreddit test --title "标题" --url https://example.com --send
```

### 2. 回复帖子（reply-post）

```
# --post 可填帖子 id 或完整 url —— dry-run
python scripts/post_reddit.py reply-post --post 1abcdef --text "回复内容"

# 真正发出
python scripts/post_reddit.py reply-post --post https://www.reddit.com/r/test/comments/1abcdef/ --text "回复内容" --send
```

### 3. 回复评论（reply-comment）

```
# --comment 填评论 id —— dry-run
python scripts/post_reddit.py reply-comment --comment dq1abc2 --text "回复内容"

# 真正发出
python scripts/post_reddit.py reply-comment --comment dq1abc2 --text "回复内容" --send
```

### 参数速查表

| 操作 | 必填参数 | 可选参数 | 说明 |
|------|---------|---------|------|
| `submit` | `--subreddit`、`--title` | `--text`（self 帖正文）/ `--url`（链接帖）、`--send` | 填 `--url` 即发链接帖；否则发 self 帖 |
| `reply-post` | `--post`（帖子 id 或 url）、`--text` | `--send` | 回复一个帖子 |
| `reply-comment` | `--comment`（评论 id）、`--text` | `--send` | 回复一条评论 |

> `--send`：**真正发出**；不加则只 dry-run 验证、不真发。所有操作通用。

---

## 五、输出格式（JSON 打到 stdout，AI 直接读）

**dry-run 输出（发帖示例）：**
```json
{"ok": true, "operation": "submit", "subreddit": "test", "title": "标题",
 "kind": "self", "text": "正文内容", "as_user": "你的用户名",
 "dry_run": true, "posted": false}
```

**--send 真发成功输出：**
```json
{"ok": true, "operation": "submit", "posted": true, "as_user": "你的用户名",
 "id": "1abcdef", "url": "https://www.reddit.com/r/test/comments/1abcdef/..."}
```

**出错输出（如缺凭据）：**
```json
{"ok": false, "error": "未找到凭据文件。请按 SKILL.md「配置步骤」创建 .secrets/reddit.json...",
 "expected_path": "...\\.secrets\\reddit.json"}
```

| 字段 | 含义 |
|------|------|
| `ok` | 操作是否成功（出错为 false） |
| `posted` | 是否真的发出（dry-run 恒为 false） |
| `dry_run` | 是否 dry-run 模式 |
| `as_user` | 当前登录的账号（验证登录拿到的用户名） |
| `operation` | submit / reply-post / reply-comment |
| `id` / `url` | 真发后新帖/新评论的 ID 和 permalink 链接 |

---

## 六、安全护栏（必读，按重要度排序）

| 护栏 | 说明 |
|------|------|
| **默认 dry-run** | 不加 `--send` 永远不真发。发前先 dry-run 确认文案、目标、登录账号正常。 |
| **发前用户确认** | 真发（`--send`）前必须把要发的完整内容给用户看、得到明确同意。 |
| **低频** | 高频发帖/回复极易触发 Reddit 反垃圾风控甚至封号。别批量刷、别短时间连发。 |
| **回复别人最易被判垃圾** | 自动/批量回复（尤其回复陌生人）是反垃圾系统重点打击对象，最容易被删、被 shadowban。回复务必极低频、人工逐条确认。 |
| **别硬广** | 直接发广告、刷推广链接会被各 subreddit 版规和反垃圾系统秒删/封号。内容要符合社区调性。 |
| **凭据安全** | 账号密码、client_secret 绝不进 git。`.secrets/` 已被 `.gitignore` 忽略；脚本只从 `.secrets/reddit.json` 读，不 hardcode、不打印密码。 |

---

## 七、已知坑 / 风险（诚实写明）

| 类别 | 说明 |
|------|------|
| **subreddit 发帖门槛** | 很多 sub 有 karma 下限、账号年龄要求、需先验证邮箱、或只允许特定 flair。门槛不够会直接报错或被删。测试可先用 r/test。 |
| **反垃圾过滤** | Reddit 的 spam filter 可能在你看不到的情况下直接删帖、把帖子打成"已移除"，甚至 shadowban（你以为发了、别人其实看不到）。新号尤其严。 |
| **新号易被限制** | 刚注册、karma 低的号发帖/回复极易被拦。建议先正常用一阵、攒点 karma 再用本 skill。 |
| **rate limit** | 短时间发太多会被 Reddit 限流报错（"you are doing that too much"）。低频操作。 |
| **登录方式** | 本 skill 用用户名+密码（PRAW 的 script app 模式）。如果账号开了两步验证（2FA），密码字段要写成 `密码:验证码` 形式，或关掉 2FA。 |
| **合规** | 自动化发帖须遵守 Reddit 用户协议和各 subreddit 版规；禁止用于垃圾营销、刷量、未授权推广。 |

---

## 八、与 reddit-research 的关系

| Skill | 干啥 | 方式 |
|-------|------|------|
| `reddit-research` | **读**：搜帖子、评论树、用户活动、痛点分析 | Arctic Shift API（免认证）等 |
| **`reddit-publish`（本 skill）** | **发**：发帖 / 回复帖子 / 回复评论 | 本机 PRAW 直连官方 API |

两者同属 Reddit skill 家族，一个读、一个写，互为姊妹 skill。

---

## 九、文件清单

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 本文档 |
| `scripts/post_reddit.py` | **主入口**：发帖/回复脚本。默认 dry-run，`--send` 才真发；结果以 JSON 打到 stdout |
| `requirements.txt` | 依赖（praw） |
| `.gitignore` | 忽略 `.secrets/`、`__pycache__/`、`*.pyc` |
| `reddit.json.example` | 凭据模板（占位值，放 skill 根目录可进 git）。真实凭据复制成 `.secrets/reddit.json`（不进 git，需各自创建） |
