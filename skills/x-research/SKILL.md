---
name: x-research
description: X（推特/Twitter）深度调研：按关键词搜推文、扒讨论、提炼用户痛点与口碑。X 没有免费公开搜索接口，且本机(国内 IP)过不了 X 反爬，所以本 skill 通过 SSH 把搜索任务发到美国硅谷服务器上跑(那台机的 twikit 环境已验证能成功搜 X)，结果 JSON 传回本机。当用户说"调研 x"、"调研 twitter"、"看看推特上怎么说 xxx"、"x 上大家对 xxx 的反馈"、"twitter 用户口碑"、"推特痛点"、"去 x 搜一下 xxx"、"twitter 上 xxx 的讨论"、"推特高赞"、"x 用户怎么看 xxx"、"twitter 口碑分析"，或做市场/产品/竞品/选品调研需要 X 数据源时触发本 skill。覆盖：SSH→服务器搜索主路径 + cookie 失效处理方向 + 痛点提取 SOP + 推文引用格式。与 reddit-research / youtube-research 同属社媒调研 skill 家族。
---

# X（推特/Twitter）调研 Skill

## 配置（第一步：设好你的账号 cookie）

本 skill 的搜索是**在硅谷服务器上执行**的，**用谁的号搜 = 你配的 cookie**。
搜索(search 角色)和发布(x-publish 的 publish 角色)是**两个独立的号**，互不影响——
你可以拿一个小号搜、用品牌号发。

**怎么配（任选一种）：**

```
# 方式 A：从本机 Firefox 自动取(先在 Firefox 登录好你要用来搜的 X 号)
python scripts/set_cookie.py --role search --from-firefox

# 方式 B：手动填(给别人 / 给别的浏览器用)
python scripts/set_cookie.py --role search --auth-token <你的auth_token> --ct0 <你的ct0>
```

**怎么从浏览器手动拿 `auth_token` / `ct0`（方式 B 用）：**
浏览器开发者工具(F12) → Application/存储 → Cookies → 选 `x.com` → 复制 `auth_token` 和 `ct0` 两个值。

**想换号：** 重新跑一次 `set_cookie.py` 即可，新 cookie 会覆盖旧的。

> ⚠️ **别拿重要品牌号做高频自动搜索**——容易被 X 限读甚至风控。搜索建议用小号。
> 工具只会打印 cookie 的前 6 位 + 长度用于核对，**不会打印 / 不会进 git 全值**。

---

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"去 x / twitter / 推特看看 xxx 的评价/反馈/讨论"
- 用户说"调研 x"、"调研 twitter"、"看看推特上怎么说 xxx"
- 用户问"x 上 xxx 的高赞推文/痛点/口碑是什么"
- 市场调研、选品调研、竞品分析需要 X 上的真实用户声音
- 用户说"twitter 用户怎么看 xxx"、"推特口碑分析"
- 产品调研需要从推文提取用户痛点、需求、品牌偏好

---

## 二、架构：为什么走服务器？

```
本机(search_x.py 编排器)
   │  ① 读 .secrets/server.json 拿连接信息
   │  ② SSH 连硅谷服务器(paramiko)
   │  ③ SFTP 上传远程搜索脚本到服务器临时目录
   ▼
硅谷服务器 47.251.0.142 (C:\AIInfoHub)
   │  ④ 用服务器 venv 跑 twikit 搜 X(cookie 在服务器上)
   │  ⑤ 输出 JSON
   ▼
本机 stdout(给 AI 读) ⑥ 删除远程临时脚本 → 关连接
```

**为什么不在本机直接跑 twikit？**
- X 没有免费公开搜索接口，官方 API 收费且门槛高。
- 本机(国内 IP)直连 X **过不了反爬**，twikit 本机路线实测确认不通。
- 硅谷服务器 IP 干净 + cookie 有效 + 已被 ai-infohub 打过 twikit 补丁 → 能稳定搜出真实推文。

所以本 skill 的 `search_x.py` 只是个**编排器(orchestrator)**：把搜索任务发到服务器执行，取回结果。真正干活的 twikit 跑在服务器上。

---

## 三、主路径：search_x.py（走服务器）

### 0. 一次性准备

**(a) 本机装依赖：**
```
pip install -r requirements.txt
# 或： pip install paramiko --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

**(b) 准备服务器连接配置 `.secrets/server.json`：**
```json
{"host": "47.251.0.142", "port": 22, "user": "Administrator", "password": "服务器密码"}
```
> ⚠️ `.secrets/` 已被 `.gitignore` 忽略，**不进 git、不会同步给团队其他人**。
> 团队其他成员 / Codex 要用本 skill，**必须各自手动创建这个文件**(密码找负责人要)。

### 1. 搜推文（主力命令）

```
python scripts/search_x.py "关键词"
python scripts/search_x.py "smart glasses" --count 30 --product Latest
```

**参数速查表：**

| 参数 | 说明 | 默认 |
|------|------|------|
| `query` | 搜索关键词（位置参数，必填） | — |
| `--count N` | 返回推文条数 | 20 |
| `--product Latest` | 按时间排序（适合看最新动态/事件监控） | **Latest** |
| `--product Top` | 按热度排序（最适合挖高互动讨论） | — |
| `--product Media` | 只看带图/视频的推文 | — |

**输出格式（JSON 打到 stdout，AI 直接读）**，结构为
`{"query": "...", "count": N, "tweets": [...]}`，每条 tweet 含：

| 字段 | 含义 |
|------|------|
| `author` | 作者用户名（@后面那个，如 `johndoe`） |
| `author_name` | 作者显示名 |
| `text` | 推文正文 |
| `likes` / `retweets` / `replies` / `quotes` / `views` | 互动数据 |
| `created_at` | 发布时间 |
| `lang` | 语种 |
| `tweet_id` | 推文 ID |
| `url` | 推文链接 `https://x.com/<user>/status/<id>` |

（字段以服务器上 twikit 2.3.3 的 Tweet 对象为准；远程脚本用 getattr 兜底，单字段缺失不会让整个脚本崩。）

---

## 四、痛点提取 SOP

拿到 search_x.py 输出的 JSON 后，按以下步骤结构化。
（数据源 = **推文本身 + 高互动推文**；reddit 是帖子+评论树，X 这里是高 likes/replies 的推文。）

### 第一步：高价值推文筛选

筛选条件：`likes ≥ 20` **或** `replies ≥ 10` **或** `retweets ≥ 10`，优先处理这些高互动推文。
（数值阈值按话题热度自行调整——冷门话题可降到 likes ≥ 5。）

### 第二步：痛点-需求映射表

| 痛点描述 | 出现频次 | 代表性原文（英文） | 关联需求 |
|---------|---------|-----------------|---------|
| 例：抱怨智能眼镜续航太短 | 14次 | "battery dies in 2 hours" | 更大电池/快充 |

### 第三步：品牌口碑矩阵

| 品牌/产品名 | 提及次数 | 正面评价要点 | 负面评价要点 |
|-----------|---------|------------|------------|
| 例：Ray-Ban Meta | 9次 | 外观自然、拍照方便 | 续航短、隐私担忧 |

### 第四步：输出格式（遵循 Protocol B 规范）

```
## 调研结论
[核心发现，3-5 句话]

## 关键痛点（按频次排序）
1. [痛点] — 出现 X 次 — 代表推文：[链接]
2. ...

## 品牌/产品提及
[品牌口碑矩阵]

## 矛盾与不确定
[不同用户意见分歧的地方]

## 来源清单
[按引用格式列出所有推文]
```

---

## 五、来源引用格式（强制）

每条推文必须按如下格式引用：

```
- "推文原话（英文）" / "中文翻译" — @用户名 (likes: X, retweets: Y, replies: Z, YYYY-MM-DD) — https://x.com/用户名/status/推文ID
```

示例：

```
- "battery dies in 2 hours, useless" / "续航 2 小时就没电，没法用" — @techreviewer (likes: 142, retweets: 18, replies: 25, 2026-06-20) — https://x.com/techreviewer/status/1234567890123456789
```

---

## 六、已知坑 / 风险（诚实写明）

| 类别 | 说明 |
|------|------|
| **依赖服务器可用** | 搜索全靠硅谷服务器(47.251.0.142)在线 + SSH 22 端口可达。服务器宕机/网络不通 → 搜不了。报错先判断是不是 SSH 连不上。 |
| **服务器限流** | 服务器对密集新连接有限流，握手可能失败。search_x.py 已内置 1 次退避重连(等 5 秒)。仍失败就隔一会儿再试。 |
| **cookie 会过期** | cookie 在服务器 `C:\AIInfoHub\data\cookies.json`，由 **ai-infohub 维护**。失效后远程脚本会报"未登录/过期"。**需在服务器上更新 cookie**(不是本机)，找 ai-infohub 负责人刷新。 |
| **依赖 twikit 补丁** | 服务器 venv 里的 twikit 2.3.3 已被 `C:\AIInfoHub\patch_twikit.py` 打过补丁(持久状态)。若 ai-infohub 重装 venv 没重打补丁，可能搜不出。 |
| **非官方库** | twikit 调的是 X 内部接口，非官方授权。X 一旦改接口可能突然失效。 |
| **账号封禁风险** | 高频调用可能触发 X 风控甚至封号。低频使用，别拿主账号狂刷。 |
| **凭据安全** | 服务器密码、cookie **绝不能进 git**。`.secrets/` 已被 `.gitignore` 忽略；脚本只从 `.secrets/server.json` 读连接信息，不 hardcode；不打印密码、不打印 cookie。 |
| **合规** | 自动化抓取属 X ToS 灰色地带，一次性市场研究通常被默许但无保证；禁止用于未授权的 AI 训练等用途。 |

---

## 七、与其他社媒调研 skill 的关系

| Skill | 数据源 | 取数方式 |
|-------|--------|---------|
| `reddit-research` | Reddit 帖子/评论 | Arctic Shift API（免认证 WebFetch） |
| `youtube-research` | YouTube 视频/评论 | 见该 skill |
| **`x-research`（本 skill）** | X 推文 | SSH 到硅谷服务器跑 twikit（服务器持 cookie） |

三者风格统一：决策树选路 → 取数 → 痛点提取 SOP → 强制引用格式。做综合社媒调研时可并用。

---

## 八、文件清单

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 本文档 |
| `scripts/search_x.py` | **主入口**：SSH 编排器，把搜索发到服务器执行并取回 JSON |
| `scripts/login_export_cookies.py` | **已废弃**：旧的本机 twikit 登录路线(本机过不了反爬，已确认不通)，仅留历史记录 |
| `requirements.txt` | 本机依赖（paramiko） |
| `.gitignore` | 忽略 `.secrets/` 等凭据文件 |
| `.secrets/server.json` | 服务器连接信息(host/port/user/password)，**不进 git，需各自创建** |
