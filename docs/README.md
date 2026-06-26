# 从这里开始 — 社媒"读+发"工具项目文档索引

> 这是一套让 AI 能在聊天里直接调研社媒数据、并往社媒发内容的工具，
> 全部做成 Claude Code skill，放在本仓库 `skills/` 目录里。
> 如果你是第一次接触这个项目，从本文件看起。

---

## 该看哪篇

| 文件 | 一句话用途 |
|------|-----------|
| **本文件 (README.md)** | 入口 / 索引 / 当前状态速览 |
| [01-overview-and-status.md](01-overview-and-status.md) | 项目背景 + 6 个 skill 各自的成败详情 |
| [02-architecture.md](02-architecture.md) | 每个 skill 怎么实现的、数据怎么流转（含服务器架构） |
| [03-decisions.md](03-decisions.md) | 为什么这么做——关键决策 + 背后的理由 |
| [04-pitfalls-and-solutions.md](04-pitfalls-and-solutions.md) | **踩坑台账**（最宝贵）：每个坑的现象 → 根因 → 解法 |
| [05-setup-and-usage.md](05-setup-and-usage.md) | 接手者怎么上手：凭据、配置、各 skill 指引 |
| [06-open-items-next-steps.md](06-open-items-next-steps.md) | 还没做完的事 + 建议的接续路径 |

---

## 当前状态速览

| 平台 | 方向 | 状态 | 说明 |
|------|------|------|------|
| Reddit | 读 | ✅ 可用 | Arctic Shift API，免认证，已实测 |
| Reddit | 发 | ⏸️ 暂缓 | 代码完成，待账号（API 准入门槛 + 账号无密码） |
| YouTube | 读 | ✅ 可用 | 官方 Data API v3，免费 key，已实测 |
| YouTube | 发 | ✅ 可用 | OAuth2 授权，已实测真发 + 删除验证 |
| X（推特） | 读 | ⚠️ 受限 | 走服务器搜索，@Quriov 被临时限读（写能成） |
| X（推特） | 发 | ✅ 可用 | 走服务器 twikit，已实测真发 + 删除验证 |

> ⚠️ X 读的受限原因：@Quriov 品牌号用来高频搜索导致 X 限读（写仍正常）。
> 解法：用 `set_cookie.py --role search` 换个小号，或等恢复。
