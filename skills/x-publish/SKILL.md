---
name: x-publish
description: 往 X（推特/Twitter）发推 + 回复推文/评论。本机(国内 IP)过不了 X 反爬，所以本 skill 通过 SSH 把发推/回复任务发到美国硅谷服务器上跑(那台机的 twikit 环境已验证能成功操作 X，与 x-research 同一台机、同一份 cookie)。发出的内容是以服务器那个 cookie 账号(ai-infohub)的身份发的。当用户说"发推"、"发条推文"、"发到 x"、"发到 twitter"、"发到推特"、"在 x 上发 xxx"、"帮我发个推文"、"推特发条 xxx"、"回复这条推文"、"回复这条评论"、"在 x 上回复 xxx"、"给这条推文回个 xxx"时触发本 skill。安全门：默认 dry-run(只验证不真发)，必须显式加 --send 才真正发出。与 x-research 同属 X 操作 skill 家族(那个负责搜，这个负责发)。
---

# X（推特/Twitter）发推 / 回复 Skill

## 配置（第一步：设好你的账号 cookie）

本 skill 的发推 / 回复是**在硅谷服务器上执行**的，**用谁的号发 = 你配的 cookie**。
发布(publish 角色)和搜索(x-research 的 search 角色)是**两个独立的号**，互不影响——
你可以拿品牌号发、用小号搜。

**怎么配（任选一种）：**

```
# 方式 A：从本机 Firefox 自动取(先在 Firefox 登录好你要用来发的 X 号)
python scripts/set_cookie.py --role publish --from-firefox

# 方式 B：手动填(给别人 / 给别的浏览器用)
python scripts/set_cookie.py --role publish --auth-token <你的auth_token> --ct0 <你的ct0>
```

**怎么从浏览器手动拿 `auth_token` / `ct0`（方式 B 用）：**
浏览器开发者工具(F12) → Application/存储 → Cookies → 选 `x.com` → 复制 `auth_token` 和 `ct0` 两个值。

**想换号：** 重新跑一次 `set_cookie.py` 即可，新 cookie 会覆盖旧的。

> ⚠️ 发出的内容是以**你配的 publish cookie 那个账号**的身份发的。每次真发前都要让用户知情确认。
> 工具只会打印 cookie 的前 6 位 + 长度用于核对，**不会打印 / 不会进 git 全值**。

---

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"发推"、"发条推文"、"发到 x / twitter / 推特"
- 用户说"帮我发个推文 xxx"、"在 x 上发 xxx"、"推特发条 xxx"
- 用户说"回复这条推文 / 评论"、"在 x 上回复 xxx"、"给这条推文回个 xxx"

> ⚠️ **重要前提**：发出的内容是以**服务器那个 cookie 账号(ai-infohub)**的身份发的。
> 不是用户的私人账号。动手前必须让用户知情并确认。

---

## 二、架构：为什么走服务器？

```
本机(post_x.py 编排器)
   │  ① 读 .secrets/server.json 拿连接信息
   │  ② SSH 连硅谷服务器(paramiko)
   │  ③ SFTP 上传远程发推/回复脚本到服务器临时目录
   ▼
硅谷服务器 47.251.0.142 (C:\QuriovXTools)
   │  ④ 用服务器 venv 跑 twikit 发推/回复(cookie 在服务器上)
   │  ⑤ 输出 JSON
   ▼
本机 stdout(给 AI 读) ⑥ 删除远程临时脚本 → 关连接
```

**为什么不在本机直接跑 twikit？** 同 x-research：本机(国内 IP)直连 X 过不了反爬，
twikit 本机路线实测不通；硅谷服务器 IP 干净 + cookie 有效 + 已打过 twikit 补丁 → 能稳定操作。

所以 `post_x.py` 只是个**编排器**：把发推任务发到服务器执行，取回结果。真正干活的 twikit 跑在服务器上。

---

## 三、主路径：post_x.py（走服务器）

### 0. 一次性准备

**(a) 本机装依赖：**
```
pip install -r requirements.txt
# 或： pip install paramiko --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

**(b) 准备服务器连接配置 `.secrets/server.json`：**
最省事的办法：把 skill 根目录的 `server.json.example` 复制到 `.secrets\server.json`，
把 `password` 换成真实密码(找负责人要)。文件内容长这样：
```json
{"host": "47.251.0.142", "port": 22, "user": "Administrator", "password": "服务器密码"}
```
> ⚠️ `.secrets/` 已被 `.gitignore` 忽略，**不进 git、不会同步给团队其他人**。
> 团队其他成员 / Codex 要用本 skill，**必须各自手动创建这个文件**(密码找负责人要)。

### 1. 发推 / 回复（主力命令）

```
# 发新推 —— 默认 dry-run，只验证不真发
python scripts/post_x.py --text "Hello from our smart glasses team!"

# 发新推 —— 真正发出
python scripts/post_x.py --text "Hello from our smart glasses team!" --send

# 回复某条推文 —— dry-run
python scripts/post_x.py --text "Thanks for the feedback!" --reply-to 1234567890123456789

# 回复某条推文 —— 真正发出
python scripts/post_x.py --text "Thanks for the feedback!" --reply-to 1234567890123456789 --send
```

**参数速查表：**

| 参数 | 说明 | 默认 |
|------|------|------|
| `--text TEXT` | 要发的推文/回复正文(必填) | — |
| `--reply-to ID` | 回复目标推文 ID；不填=发新推，填=回复该推文 | 无(发新推) |
| `--send` | **真正发出**；不加则只 dry-run 验证、不真发 | 关(dry-run) |

> 🔒 **安全门(核心设计)**：**默认 dry-run**。不加 `--send` 时，脚本只验证「能连服务器、
> cookie 能加载、create_tweet 方法存在、将要发什么」，**绝不真发**。确认无误后再加 `--send`。

### 2. 输出格式（JSON 打到 stdout，AI 直接读）

**dry-run 输出：**
```json
{"dry_run": true, "cookie_loaded": true, "create_tweet_available": true,
 "mode": "new_tweet", "would_post_text": "...", "reply_to": null, "posted": false}
```

**--send 真发成功输出：**
```json
{"posted": true, "mode": "new_tweet", "id": "1234567890123456789",
 "reply_to": null, "url": "https://x.com/i/status/1234567890123456789"}
```

| 字段 | 含义 |
|------|------|
| `posted` | 是否真的发出(dry-run 恒为 false) |
| `dry_run` | 是否 dry-run 模式 |
| `cookie_loaded` / `create_tweet_available` | dry-run 校验项 |
| `mode` | `new_tweet`(发新推) / `reply`(回复) |
| `would_post_text` | dry-run 下将要发的内容 |
| `id` / `url` | 真发后的推文 ID 和链接 |
| `reply_to` | 回复目标推文 ID(发新推为 null) |

---

## 四、安全护栏（必读，按重要度排序）

| 护栏 | 说明 |
|------|------|
| **默认 dry-run** | 不加 `--send` 永远不真发。发前先 dry-run 确认文案、模式、cookie 正常。 |
| **发前用户确认** | 真发(`--send`)前必须把要发的完整内容给用户看、得到明确同意。内容是以 ai-infohub 账号身份发的，不可随意。 |
| **低频** | 高频发推/回复极易触发 X 风控甚至封号。别批量刷、别短时间连发。 |
| **回复尤其高危** | 自动回复(尤其回复陌生人/批量回复)是 X 风控重点打击对象，最容易封号。回复务必极低频、人工逐条确认。 |
| **凭据安全** | 服务器密码、cookie 绝不进 git。`.secrets/` 已被 `.gitignore` 忽略；脚本只从 `.secrets/server.json` 读连接信息，不 hardcode；不打印密码、不打印 cookie。 |
| **账号归属知情** | 发的不是用户私人号，是服务器 cookie 账号(ai-infohub)。每次发前向用户讲清。 |

---

## 五、已知坑 / 风险（诚实写明）

| 类别 | 说明 |
|------|------|
| **依赖服务器可用** | 全靠硅谷服务器(47.251.0.142)在线 + SSH 22 可达。服务器宕机/网络不通 → 发不了。报错先判断是不是 SSH 连不上。 |
| **服务器限流** | 服务器对密集新连接有限流，握手可能失败。post_x.py 已内置 1 次退避重连(等 5 秒)。仍失败就隔一会儿再试。 |
| **cookie 会过期** | 发布 cookie 在服务器 `C:\QuriovXTools\cookies\publish.json`。失效后远程脚本会报"未登录/过期"。需在服务器上更新 publish.json(不是本机)，重新提取发布账号 cookie 并上传，或本机跑 `python scripts\set_cookie.py --role publish --from-firefox` 后同步上去。 |
| **依赖 twikit 补丁** | 服务器 venv 里的 twikit 2.3.3 已打过补丁。若重装 venv 没重打补丁，可能发不出。 |
| **非官方库** | twikit 调的是 X 内部接口，非官方授权。X 一旦改接口可能突然失效。 |
| **发推/封号风险** | 发推、尤其回复，比搜索更易触发风控。低频、人工确认、别拿主账号狂发。 |
| **合规** | 自动化发推属 X ToS 灰色地带；禁止用于垃圾营销、刷量、未授权推广等用途。 |

---

## 六、与 x-research 的关系

| Skill | 干啥 | 取数/操作方式 |
|-------|------|--------------|
| `x-research` | **搜** X 推文、提炼痛点口碑 | SSH 到硅谷服务器跑 twikit `search_tweet` |
| **`x-publish`（本 skill）** | **发** 推 / 回复推文 | SSH 到同一台硅谷服务器跑 twikit `create_tweet` |

两者同一台服务器、同一份 cookie、同一套 SSH 编排模式，互为姊妹 skill：一个读、一个写。

---

## 七、文件清单

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 本文档 |
| `scripts/post_x.py` | **主入口**：SSH 编排器，把发推/回复发到服务器执行并取回 JSON。默认 dry-run，`--send` 才真发 |
| `requirements.txt` | 本机依赖（paramiko） |
| `.gitignore` | 忽略 `.secrets/` 等凭据文件 |
| `server.json.example` | 服务器连接配置模板(占位密码)，复制到 `.secrets/server.json` 后填真实密码 |
| `.secrets/server.json` | 服务器连接信息(host/port/user/password)，**不进 git，需各自创建** |
