---
name: youtube-research
description: YouTube 深度调研：通过 YouTube Data API v3（免费、每天 1 万配额、自备免费 API key）用 WebFetch 抓取视频搜索结果、视频统计数据（播放/点赞）、视频评论，做痛点分析与口碑调研。当用户说"调研 youtube"、"看看 youtube 上 xxx"、"youtube 上大家怎么评价 xxx"、"看看 youtube 视频评论"、"youtube 用户口碑"、"youtube 用户怎么看 xxx"、"youtube 网红/博主怎么说 xxx"、"去 youtube 搜一下"、"youtube 上有哪些视频讨论 xxx"、"youtube 高赞评论"、"youtube 痛点"、"分析 youtube 数据"，或做市场/产品/竞品/选品调研需要 YouTube 数据源时触发本 skill。覆盖：主路径 Data API v3（WebFetch 直接抓，搜视频/读统计/读评论全能）+ 无 key 兜底 oEmbed + 字幕降级方案 + 已知坑 + 痛点提取 SOP + 来源引用格式。
---

# YouTube 调研 Skill

## 一、何时触发本 Skill

满足以下任一条件即启用：

- 用户说"去 youtube 看看 xxx 的评价/反馈/讨论"
- 用户说"调研 youtube xxx"、"youtube 上大家怎么评价 xxx"
- 用户问"youtube 上 xxx 的高赞评论/痛点是什么"
- 用户说"看看 youtube 视频评论"、"youtube 用户口碑分析"
- 用户说"youtube 网红/博主怎么说 xxx"、"youtube 用户怎么看 xxx"
- 市场调研、选品调研、竞品分析需要真实用户声音（YouTube 视频 + 评论）
- 产品调研需要从 YouTube 评论里提取用户痛点、需求、品牌偏好

---

## 配置（第一步：拿一个免费 API key）

> 这个 key 免费、不绑卡，每天 1 万配额。把它填进下面 URL 模板里的 `YOUR_API_KEY`。

1. 打开 https://console.cloud.google.com/ ，登录 Google 账号
2. 顶部新建/选择一个项目
3. 启用接口：https://console.cloud.google.com/apis/library/youtube.googleapis.com → 点"启用"
4. 建 key：https://console.cloud.google.com/apis/credentials → 创建凭据 → API 密钥 → 复制那串(形如 `AIzaSy...`)
5. (可选)限制该 key 只用于 YouTube Data API v3，更安全

说明：创建 API 密钥不需要绑信用卡。

---

## 二、决策树：选哪条路？

```
需要 YouTube 数据
│
├─ 有免费 API key（推荐）
│   └─► 主路径：Data API v3（WebFetch 直接抓，搜视频/读数据/读评论全能）
│
├─ 没 key，只想读单个视频的标题/作者/封面
│   └─► 兜底：oEmbed 端点（免 key，但不能搜、不能读评论）
│       https://www.youtube.com/oembed?url=视频URL&format=json
│
└─ 需要视频字幕/文字稿
    └─► 降级：官方字幕端点已被 POT token 堵死（WebFetch 抓返回空），
        改用第三方免费转写（如 youtubetotranscript.com），稳定性略差
```

---

## 三、主路径：YouTube Data API v3

**Base URL**：`https://www.googleapis.com/youtube/v3`

- **免费**，每天 1 万配额（quota）
- **需自备一个免费 API key**：去 Google Cloud Console 注册，免绑卡。建好项目 → 启用 "YouTube Data API v3" → 创建凭据（API key）即可
- **关键提示**：下面所有 URL 模板里的 `YOUR_API_KEY` 都要换成用户自己的 key；`VIDEO_ID` 换成目标视频 ID（视频 URL `https://www.youtube.com/watch?v=VIDEO_ID` 里 `v=` 后面那串）
- 直接 WebFetch 这些 URL 即可，返回 JSON

### Endpoint 速查表

| 端点 | 功能 | URL 模板 | 配额消耗 |
|------|------|---------|---------|
| `search.list` | 按关键词搜视频 | `https://www.googleapis.com/youtube/v3/search?part=snippet&q=关键词&type=video&maxResults=10&key=YOUR_API_KEY` | 100/次（每天约 100 次搜索） |
| `videos.list` | 读视频信息 + 统计数据（播放/点赞数） | `https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=VIDEO_ID&key=YOUR_API_KEY` | 1/次 |
| `commentThreads.list` | 读某视频的评论 | `https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId=VIDEO_ID&maxResults=100&key=YOUR_API_KEY` | 1/次（每天数千次） |

### 常用参数补充

**search.list 可加的筛选参数：**
- `order=viewCount` — 按播放量从高到低排（找最热视频）
- `relevanceLanguage=en` — 优先返回英文相关结果
- `publishedAfter=日期` — 只要某日期之后的视频，日期用 ISO 8601 格式，如 `2025-01-01T00:00:00Z`

**commentThreads.list 可加的参数：**
- `order=relevance`（默认，按热度/相关度，等于"高赞优先"）或 `order=time`（按时间倒序，看最新评论）
- 翻页：用上一次返回里的 `nextPageToken` 字段，拼 `&pageToken=xxx` 取下一页评论

### 模板 A：调研某关键词下的热门视频

**WebFetch URL（直接复制使用，把关键词和 key 替换掉）**：

```
https://www.googleapis.com/youtube/v3/search?part=snippet&q=tesla+front+license+plate&type=video&order=viewCount&maxResults=10&key=YOUR_API_KEY
```

返回的 JSON 里每个 item 的 `id.videoId` 就是视频 ID，`snippet.title` / `snippet.channelTitle` 是标题和频道名。挑出高价值视频 ID 进入下一步。

### 模板 B：读视频的统计数据（播放/点赞）

拿到视频 ID 后，批量读统计（id 可用逗号拼多个）：

```
https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id=VIDEO_ID1,VIDEO_ID2&key=YOUR_API_KEY
```

返回里 `statistics.viewCount`（播放量）、`statistics.likeCount`（点赞数）、`statistics.commentCount`（评论数）用来判断视频热度。

### 模板 C：抓某视频的高赞评论

对高价值视频抓评论（默认按相关度，等于高赞优先）：

```
https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId=VIDEO_ID&order=relevance&maxResults=100&key=YOUR_API_KEY
```

返回里每条评论的关键字段：
- `snippet.topLevelComment.snippet.textDisplay` — 评论原文
- `snippet.topLevelComment.snippet.authorDisplayName` — 评论者
- `snippet.topLevelComment.snippet.likeCount` — 评论点赞数
- 翻页：若返回里有 `nextPageToken`，拼 `&pageToken=该值` 继续抓下一页

并行抓多个视频的评论（各发一次 WebFetch），合并后进入痛点提取。

---

## 四、无 key 兜底：oEmbed 端点

### 何时考虑

- 用户没有 API key，又只想快速拿单个视频的标题/作者/缩略图
- 只是确认一个视频 URL 对不对、是谁发的

### 用法

```
https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=VIDEO_ID&format=json
```

**免 key、直接 WebFetch 即可**，返回 `title`（标题）、`author_name`（频道名）、`thumbnail_url`（缩略图）。

### 局限（重要）

- **不能搜视频**（没有搜索功能）
- **不能读评论**（拿不到任何评论数据）
- **不能读播放/点赞统计**
- 只能针对你已经知道 URL 的单个视频，拿最基础的元信息

调研类任务（搜视频、挖评论、提痛点）兜底不了，必须走主路径的 API key。

---

## 五、视频字幕/文字稿：降级方案

### 现状

- **YouTube 官方 timedtext 字幕端点在 2026 年被 POT token 机制堵死**，WebFetch 直接抓会返回空（拿不到字幕文本）
- 要拿视频里说了什么（文字稿），只能走第三方免费转写服务

### 降级路径

```
https://youtubetotranscript.com  →  贴入视频 URL，拿转写文字
```

- **标注为"降级可选"**：第三方服务稳定性略差，可能限流或偶尔抓不到
- **日常调研建议**：多数产品/口碑调研，只靠 **视频标题 + 高赞评论** 就足够提炼痛点，不一定需要字幕。字幕仅在需要分析"博主在视频里具体讲了什么观点"时才用

---

## 六、已知坑（诚实写明）

| 类别 | 说明 |
|------|------|
| **字幕抓不到** | YouTube 官方 timedtext 字幕端点 2026 年被 POT token 机制堵死，WebFetch 抓返回空。要拿视频文字内容只能走第三方转写（如 youtubetotranscript.com），稳定性略差，标注为"降级可选"。日常调研可只靠 标题 + 评论 提痛点 |
| **配额限制** | `search` 每次吃 **100 配额**，每天 1 万配额 ≈ 每天约 **100 次搜索**；`videos`（读信息）、`commentThreads`（读评论）每次只吃 **1 配额**，可大量调用。**搜索时省着点用**，把搜索结果挑准了再去批量读评论 |
| **无 key 兜底很弱** | oEmbed 端点免 key，但只能拿单个视频的标题/作者/缩略图，**不能搜、不能读评论、不能读统计**。真要调研必须配 API key |
| **API key 必备** | 主路径所有端点都要 `YOUR_API_KEY`，没 key 寸步难行；好在 key 免费免绑卡（Google Cloud Console 注册即得） |

---

## 七、痛点提取 SOP

数据源 = **YouTube 视频标题 + 高赞评论**。拿到 raw JSON 之后按以下步骤结构化：

### 第一步：高价值视频筛选

筛选条件：播放量高（`statistics.viewCount` 大）**或** 评论多（`statistics.commentCount` 大），优先抓这些视频的评论。

### 第二步：高赞评论优先

抓评论用 `order=relevance`（高赞优先），重点看 `likeCount` 高的评论 —— 点赞多 = 多数观众认同的真实声音。

### 第三步：痛点-需求映射表

| 痛点描述 | 出现频次 | 代表性原文（英文） | 关联需求 |
|---------|---------|-----------------|---------|
| 例：担心前车牌安装损坏保险杠 | 12 次 | "don't want to drill holes" | 免钻孔安装方案 |

### 第四步：品牌口碑矩阵

| 品牌/产品名 | 提及次数 | 正面评价要点 | 负面评价要点 |
|-----------|---------|------------|------------|
| 例：NoPlate | 8 次 | 安装简单、不留痕 | 价格偏高 |

### 第五步：输出格式（遵循 Protocol B 规范）

```
## 调研结论
[核心发现，3-5 句话]

## 关键痛点（按频次排序）
1. [痛点] — 出现 X 次 — 代表视频/评论：[链接]
2. ...

## 品牌/产品提及
[品牌口碑矩阵]

## 矛盾与不确定
[不同用户意见分歧的地方]

## 来源清单
[按引用格式列出所有视频/评论]
```

---

## 八、来源引用格式（强制）

### 视频引用格式

```
- 视频标题 — 频道名 (播放量: X, 点赞: Y, YYYY-MM-DD) — https://www.youtube.com/watch?v=VIDEO_ID
```

示例：
```
- "Tesla Front License Plate - No Drill Solution" — Tesla Tips (播放量: 152,000, 点赞: 4,300, 2025-12-30) — https://www.youtube.com/watch?v=abc123XYZ
```

### 评论引用格式

```
- "评论原话（英文）" / "中文翻译" — 评论者 (likes: Z) — 来自视频《视频标题》 https://www.youtube.com/watch?v=VIDEO_ID
```

示例：
```
- "I don't want to drill into the bumper" / "不想在保险杠上打孔" — @TeslaOwner99 (likes: 87) — 来自视频《Tesla Front License Plate》 https://www.youtube.com/watch?v=abc123XYZ
```

---

## 九、注意事项

| 类别 | 说明 |
|------|------|
| **配额省着用** | search 吃 100 配额/次，每天约 100 次搜索封顶；先把搜索做精准，再用 1 配额/次的读评论端点大量挖数据 |
| **key 安全** | API key 是用户私有凭据，不要写进任何会被提交/分享的文件，调研用完即可 |
| **字幕不强求** | 官方字幕端点已失效，日常调研靠 标题 + 评论 即可，字幕走第三方仅作降级 |
| **数据真实** | 以上端点均为 YouTube Data API v3 真实端点，不要臆造不存在的端点或参数 |

---

## 十、参考链接

1. **YouTube Data API v3 官方文档**：https://developers.google.com/youtube/v3/docs
2. **search.list 文档**：https://developers.google.com/youtube/v3/docs/search/list
3. **videos.list 文档**：https://developers.google.com/youtube/v3/docs/videos/list
4. **commentThreads.list 文档**：https://developers.google.com/youtube/v3/docs/commentThreads/list
5. **配额与计算器**：https://developers.google.com/youtube/v3/determine_quota_cost
6. **oEmbed 端点**：https://www.youtube.com/oembed
7. **第三方转写（降级）**：https://youtubetotranscript.com
