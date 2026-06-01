---
name: reddit-research
description: Reddit 深度调研：通过 Arctic Shift API（免认证、已实测可用）抓取 subreddit 帖子、评论树、用户活动、痛点分析。当用户说"调研 reddit"、"看看 r/xxx"、"reddit 用户怎么看"、"reddit 上 xxx 的反馈"、"reddit 痛点"、"reddit 高赞帖"、"reddit 评论"、"reddit 口碑"、"去 reddit 搜一下"、"reddit 有哪些讨论"、"reddit 用户说什么"、"分析 reddit 数据"，或做市场/产品/竞品/选品调研需要 Reddit 数据源时触发本 skill。覆盖：主路径 Arctic Shift（免认证实测可用）+ 备路径 reddit-mcp-buddy OAuth / Apify 付费 / Academic Torrents 历史档案 + 完整 Fallback Chain + 痛点提取 SOP + 来源引用格式。已实测（2026-06）：Arctic Shift 可用、reddit-mcp-buddy 匿名模式不可用（需 OAuth）。
---

# Reddit 调研 Skill

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"去 reddit 看看 xxx 的评价/反馈/讨论"
- 用户说"调研 r/xxx"、"看看 r/xxx 怎么说"
- 用户问"reddit 上 xxx 的高赞帖/评论/痛点是什么"
- 市场调研、选品调研、竞品分析需要真实用户声音
- 用户说"reddit 用户怎么看 xxx"、"reddit 口碑分析"
- 产品调研需要提取用户痛点、需求、品牌偏好

---

## 二、决策树：选哪条路？

```
需要 Reddit 数据
│
├─ 一次性调研，< 1000 帖，不想配账号
│   └─► 主路径：Arctic Shift API（直接 WebFetch，免认证）
│
├─ 需要工具调用（MCP 风格调研）
│   └─► 备路径 1：reddit-mcp-buddy + OAuth（需申请账号）
│
├─ 不想自建，愿意付费
│   └─► 备路径 2：Apify Fast Reddit Scraper（$2/1k）
│
└─ 需要 GB 级历史数据（2005-2024）
    └─► 备路径 3：Academic Torrents 3.28 TB 档案
```

---

## 三、主路径：Arctic Shift API

**Base URL**：`https://arctic-shift.photon-reddit.com`

- **无需认证**，直接 WebFetch
- 速率上限：每秒几次没问题，监控 `X-RateLimit-Remaining` 响应头
- **数据滞后约 36 小时**，不适合实时监控
- 合规注意：社区档案，未经 Reddit 许可运营，商用属灰色地带

### Endpoint 速查表

| 端点 | 功能 | 关键参数 |
|------|------|---------|
| `/api/posts/search` | 搜帖子 | subreddit, title, body, author, flair, limit(1-100 或 "auto" 返回 100-1000), before, after |
| `/api/comments/search` | 搜评论 | 同上 |
| `/api/comments/tree?link_id=<id>` | 拿某帖完整评论树（含折叠评论） | link_id（帖子 ID，如 t3_abc123） |
| `/api/posts/ids` | 批量按 ID 取帖子 | 每次最多 500 个 |
| `/api/comments/ids` | 批量按 ID 取评论 | 每次最多 500 个 |
| `/api/posts/search/aggregate` | 帖子聚合统计 | groupBy: date/author/subreddit |
| `/api/comments/search/aggregate` | 评论聚合统计 | groupBy: date/author/subreddit |
| `/api/time_series` | 时间序列趋势 | 关键词随时间的讨论量变化 |

### 模板 A：调研某 sub 关于关键词的痛点

**WebFetch URL（直接复制使用，把关键词替换掉）**：

```
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=TeslaModel3&title=license+plate&limit=20
```

多个 subreddit 并行抓（各发一次 WebFetch）：
```
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=TeslaModel3&title=license+plate&limit=20
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=TeslaModelY&title=license+plate&limit=20
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=teslamotors&title=license+plate&limit=20
```

**拿到结果后的提取 prompt**：

```
对以上 JSON 数据，提取：
1. 用户痛点清单（按出现频次从高到低排列）
2. 品牌/产品提及次数统计
3. 价格相关讨论（只提取含具体数字的）
4. 高热度帖子列表（score > 5 或 num_comments > 10）
   格式：标题 | score | 评论数 | 日期 | 帖子 ID
```

**实测返回数据样本（r/TeslaModel3 + license plate，2026-01）**：
- "License plate holder" — score 7，**65 条评论**，2025-12-30（高热度）
- "Just got a ticket for not having a front license plate" — score N/A，2025-12-31
- "Is there any reason you would not use a tow-hook front license plate mount?" — score 3，15 条评论
- "License Plate Screws?" — score 10，15 条评论

### 模板 B：跨多个 sub 关键词搜索

适合：关键词不只出现在标题，还在帖子正文讨论中。

```
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=TeslaModel3&body=license+plate+holder&limit=30
https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=TeslaModelY&body=no+drill+mount&limit=30
```

并行发出多个 WebFetch，合并去重后提取。

### 模板 C：抓某帖完整评论树

先从模板 A/B 结果中找到高价值帖子的 ID（JSON 里的 `id` 字段，格式如 `1hycr7n`），然后：

```
https://arctic-shift.photon-reddit.com/api/comments/tree?link_id=t3_1hycr7n
```

注意：`link_id` 前必须加 `t3_` 前缀。该端点返回含折叠评论的完整讨论树，适合挖掘具体产品推荐和真实用户反馈。

---

## 四、备路径 1：reddit-mcp-buddy（需 OAuth）

### 何时考虑

- 需要工具调用风格（browse_subreddit / search_reddit 等）
- 需要超过 100 次/分钟的速率
- **⚠️ 匿名模式 2026-06 实测不可用**：任何 subreddit 调用返回 "Cannot access r/X - private/quarantined"（实际并非私密），根因是 Reddit 已封匿名 API token

### 配置步骤

1. 申请 Reddit App：https://www.reddit.com/prefs/apps → "create another app..." → type=script → redirect_uri=http://localhost:8080（注意：2026-06 部分地区/账号申请流程有门槛）
2. 获取 Client ID 和 Client Secret
3. 注册 MCP：

```
claude mcp remove reddit-mcp-buddy -s user
claude mcp add --transport stdio reddit-mcp-buddy -s user -e REDDIT_CLIENT_ID=你的ID -e REDDIT_CLIENT_SECRET=你的密钥 -- npx -y reddit-mcp-buddy
```

### 5 个工具速查

| 工具 | 功能 |
|------|------|
| `browse_subreddit` | 浏览指定 sub 的 hot/top/new 帖子 |
| `search_reddit` | 跨 sub 关键词搜索 |
| `get_post_details` | 拿帖子详情 + 评论树 |
| `user_analysis` | 分析某用户活动 |
| `reddit_explain` | 解释 Reddit 特有术语/梗 |

---

## 五、备路径 2：Apify Fast Reddit Scraper（付费兜底）

- **URL**：https://apify.com/practicaltools/apify-reddit-api
- **定价**：$2.00 / 1000 条结果；首月 1000 条免费
- **适合**：紧急 + 一次性 + 不想配账号
- **⚠️ 黑盒警告**：底层机制未知，不保证走官方 OAuth2，合规性无法验证

---

## 六、备路径 3：Academic Torrents 历史档案

- **URL**：https://academictorrents.com/details/1614740ac8c94505e4ecb9d88be8bed7b6afddd4
- **规格**：3.28 TB，top 40,000 subreddits，2005-06 至 2024-12，zstandard 压缩 ndjson
- **适合**：需要 GB 级历史 sweep、离线分析、学术研究
- **解析工具**：https://github.com/Watchful1/PushshiftDumps（481 stars，提取指定 subreddit 的脚本）

---

## 七、Fallback Chain（优先级 1 → 6）

```
1. Arctic Shift API（WebFetch 直接调用，免认证）
   ↓ 端点报错 / 数据不够
2. Arctic Shift Web UI 人工浏览（arctic-shift.photon-reddit.com/search）
   ↓ 需要工具调用 / 速率升级
3. reddit-mcp-buddy + OAuth（60-100 req/min）
   ↓ 需要完整评论树深度控制
4. hawstein/mcp-server-reddit（OAuth，支持 depth 1-10 评论树）
   ↓ 需要 GB 级历史数据
5. Academic Torrents 3.28 TB（torrent 下载 + 离线解析）
   ↓ 紧急 + 一次性 + 愿意付费
6. Apify Fast Reddit Scraper（$2/1k，黑盒付费兜底）
```

---

## 八、痛点提取 SOP

拿到 raw JSON 之后按以下步骤结构化：

### 第一步：高价值帖子筛选

筛选条件：score ≥ 5 **或** num_comments ≥ 10，优先处理这些帖子的评论树。

### 第二步：痛点-需求映射表

| 痛点描述 | 出现频次 | 代表性原文（英文） | 关联需求 |
|---------|---------|-----------------|---------|
| 例：担心前车牌安装损坏保险杠 | 12次 | "don't want to drill holes" | 免钻孔安装方案 |

### 第三步：品牌口碑矩阵

| 品牌/产品名 | 提及次数 | 正面评价要点 | 负面评价要点 |
|-----------|---------|------------|------------|
| 例：NoPlate | 8次 | 安装简单、不留痕 | 价格偏高 |

### 第四步：输出格式（遵循 Protocol B 规范）

```
## 调研结论
[核心发现，3-5 句话]

## 关键痛点（按频次排序）
1. [痛点] — 出现 X 次 — 代表帖子：[链接]
2. ...

## 品牌/产品提及
[品牌口碑矩阵]

## 矛盾与不确定
[不同用户意见分歧的地方]

## 来源清单
[按引用格式列出所有帖子]
```

---

## 九、来源引用格式（强制）

每条帖子/评论必须按如下格式引用：

```
- "用户原话（英文）" / "中文翻译" — r/sub_name [帖子ID] (score: X, comments: Y, YYYY-MM-DD) — https://reddit.com/r/sub/comments/帖子ID/
```

示例：
```
- "I don't want to drill into the bumper" / "不想在保险杠上打孔" — r/TeslaModel3 [1hycr7n] (score: 7, comments: 65, 2025-12-30) — https://reddit.com/r/TeslaModel3/comments/1hycr7n/
```

---

## 十、注意事项

| 类别 | 说明 |
|------|------|
| **数据时效** | Arctic Shift 滞后约 36 小时，不适合实时事件监控 |
| **匿名模式** | reddit-mcp-buddy 匿名模式 2026-06 实测失败，必须配 OAuth |
| **合规灰色** | Arctic Shift / Academic Torrents 均未经 Reddit 明确授权，一次性市场研究通常被默许但无保证 |
| **禁止用途** | Reddit 2024+ ToS 明确禁止未授权用于 AI 训练 |
| **废弃方案** | Pushshift.io（2023-04 关闭）、旧版 PRAW 教程（2023 前已过时）不要使用 |

---

## 十一、参考链接

1. **完整调研报告**：`D:\Workspace\项目调研\美国特斯拉车牌支架调研\doc\reddit-anti-scrape-research.md`（106 个子 agent，2026-06 实测）
2. **Arctic Shift GitHub**：https://github.com/ArthurHeitmann/arctic_shift
3. **Arctic Shift Web UI**：https://arctic-shift.photon-reddit.com/search
4. **reddit-mcp-buddy**：https://github.com/karanb192/reddit-mcp-buddy
5. **Academic Torrents 档案**：https://academictorrents.com/details/1614740ac8c94505e4ecb9d88be8bed7b6afddd4
6. **PushshiftDumps 解析工具**：https://github.com/Watchful1/PushshiftDumps
