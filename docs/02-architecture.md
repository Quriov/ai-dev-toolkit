# 架构说明：每个 Skill 怎么实现的

> 本篇说明：两类（读/发）工具各自的实现方式，重点讲为什么 X 要走服务器，
> 以及服务器独立工具箱 `C:\QuriovXTools\` 的结构和数据流。

---

## 一、整体分类

| 实现方式 | 适用 Skill |
|---------|-----------|
| **纯文档 SOP + WebFetch** | `reddit-research`（Arctic Shift API）、`youtube-research`（官方 Data API） |
| **本机直接跑脚本** | `reddit-publish`（PRAW 直连） |
| **OAuth 授权 + 本机脚本** | `youtube-publish`（Google OAuth2） |
| **SSH → 海外服务器执行** | `x-research`（搜推文）、`x-publish`（发推文） |

---

## 二、Reddit 读：Arctic Shift API（最简单）

```
AI 的 WebFetch 工具
   → 直接请求 Arctic Shift 的端点
   → 拿回 JSON，AI 解析提炼
```

- 完全免认证，不需要任何账号或 key。
- AI 只用自带的 WebFetch 能力，无需脚本。
- 数据滞后约 36 小时（正常，不影响市场调研类用途）。

---

## 三、YouTube 读：官方 Data API v3（同样简单）

```
AI 的 WebFetch 工具（带用户的 API key）
   → 请求 googleapis.com 的端点
   → 搜视频 / 读统计 / 读评论
```

- 需要用户自备一个免费 API key（Google Cloud Console，5 分钟，不绑卡）。
- AI 把 key 拼进 URL，直接 WebFetch，无需脚本。

---

## 四、YouTube 发：OAuth2 本机直接调（重要：纯标准库）

```
本机 post_comment.py（纯 stdlib urllib）
   → 读 .secrets/token.json（OAuth2 令牌）
   → 直接调 YouTube Data API v3 写端点（googleapis.com）
   → 返回评论 ID / 回复 ID
```

**为什么不用 requests 库**：本机 Python 的 requests/urllib3 连 Google 会崩（`SSL: UNEXPECTED_EOF`），这是本机网络环境的问题。curl 和 Python 标准库 urllib 都正常。所以 youtube-publish 整套改成纯标准库实现，`requirements.txt` 为空（无第三方依赖）。

---

## 五、X 读 + 发：SSH 到海外服务器执行（最复杂，看清楚）

这是整个项目里最重要的架构，解释为什么 X 要这么绕。

### 为什么要走服务器？

X（推特）没有免费公开搜索接口，官方 API 收费且门槛高。业界用的是 twikit（非官方库，用账号 cookie 登录），但有两层挑战：

1. **twikit 有反爬 bug**：`Couldn't get KEY_BYTE indices` 报错——X 后端要求一个动态 transaction-id，twikit 的正则解析过时了，解不出来。PyPI 最新版和 GitHub 开发版都有这个问题，要打补丁才能用。
2. **国内 IP 被 X 屏蔽**：即使装了 TUN 代理，X 对数据中心 IP 发 Arkose 挑战页，或影子屏蔽（返回 200+空数据，不报错）。只有美国阿里云的 IP 能稳定过。

结论：X 的搜索/发推，必须在那台海外服务器上跑。

### 数据流（6 步）

```
本机 search_x.py / post_x.py（编排器）
   │  ① 读 .secrets/server.json 拿服务器连接信息
   │  ② paramiko SSH 连服务器（47.251.0.142:22）
   │  ③ SFTP 上传临时执行脚本到服务器 temp 目录
   ▼
硅谷服务器 47.251.0.142（Windows Server 2025）
   │  ④ 激活 C:\QuriovXTools\.venv
   │     跑 twikit（已打补丁 + cookie 已就绪）
   │  ⑤ 结果以 JSON 写到 stdout
   ▼
本机 ⑥ 读回 JSON 打印给 AI → 删除临时脚本 → 关连接
```

### 服务器独立工具箱：`C:\QuriovXTools\`

这是一个独立的工具箱目录，专门给这两个 X skill 用。**和 `C:\AIInfoHub\`（自动日报管线）完全分开**，互不影响。

```
C:\QuriovXTools\
├── .venv\               独立虚拟环境（已打补丁的 twikit 2.3.3）
├── cookies\
│   ├── search.json      搜索用的 X 账号 cookie（x-research 用）
│   └── publish.json     发布用的 X 账号 cookie（x-publish 用）
└── patch_twikit.py      反爬补丁脚本（修 transaction-id 正则 + get_indices）
```

**为什么独立，不复用 AIInfoHub？**

| | `C:\AIInfoHub\` | `C:\QuriovXTools\` |
|---|---|---|
| 用途 | 自动定时日报管线（关注账号推文） | 交互式搜索 + 按需发推 |
| 账号 | 固定的 ai-infohub 账号 cookie | 可配多个角色（search / publish） |
| 管理 | ai-infohub 仓库维护 | 本项目维护 |
| 影响 | 碰坏了日报跑不了 | 只影响本项目 |

独立的目的：互不干扰，换 cookie 或更新补丁不影响日报管线。

### cookie 管理

搜索和发布用**两个独立的 cookie 文件**，互不影响：
- 可以拿一个小号搜（`cookies\search.json`）
- 用品牌号发（`cookies\publish.json`）

换 cookie 用 `set_cookie.py`（两个 X skill 都带这个脚本）：
```
python scripts/set_cookie.py --role search --from-firefox
python scripts/set_cookie.py --role publish --from-firefox
```

---

## 六、Reddit 发：本机直连（最简单的"发"）

```
本机 post_reddit.py（PRAW 库）
   → 读 .secrets/reddit.json（账号凭据）
   → 直接调 Reddit 官方 API
```

Reddit 有官方 API，本机国内 IP 可直连，不需要服务器。**但目前暂缓**——账号用 Google 登录没有密码，PRAW 的 script 模式需要密码，卡在这一步（详见踩坑台账）。

---

## 七、凭据安全约定

所有 skill 的凭据都存在各自 skill 目录下的 `.secrets/` 里，全部被 `.gitignore` 忽略，**绝不进 git**。

| Skill | 凭据文件 | 内容 |
|-------|---------|------|
| x-research / x-publish | `.secrets/server.json` | 服务器 IP / 端口 / 用户名 / 密码 |
| youtube-publish | `.secrets/client_secret.json` + `.secrets/token.json` | Google OAuth 凭据 + 授权令牌 |
| reddit-publish | `.secrets/reddit.json` | Reddit 账号凭据（client_id / client_secret / 用户名 / 密码） |

找凭据：找团队负责人要，或见各 skill 目录下的 `server.json.example` / `reddit.json.example` 模板文件（模板里是占位值，不是真实凭据）。
