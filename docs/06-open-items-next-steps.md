# 未完成事项与接续路径

> 本篇说明：这个项目截至 2026-06-26 还没做完的事，以及建议的接续方向。
> 如果你是继续推进这个项目的人，从这里找到起点。

---

## 一、待完成项（按优先级）

### 1. 合并 PR #4（等用户 review）

**状态**：PR 已开，未合并。
**内容**：整合 x-research / x-publish / youtube-publish 的最新版本（QuriovXTools 迁移 + set_cookie 工具 + urllib 重写），并补了各 skill SKILL.md 的文档修正。
**下一步**：用户 review 无问题后合并。

---

### 2. reddit-publish 真发测试

**阻碍**：账号用 Google 登录没有独立密码，PRAW 的 script 模式无法使用。
**选项**：
- **A（推荐）**：在 Reddit 账号设置里添加独立密码，然后跑 `post_reddit.py --send` 测真发。
- **B**：注册一个新的 Reddit 账号（直接用用户名+密码注册），配好 `client_id / client_secret`，测发帖。
- **C（备选）**：研究 PRAW 的浏览器 cookie 认证方式，绕过密码要求。

**附注**：代码逻辑（PRAW 操作、dry-run 安全门、JSON 输出）已经完整，纯粹卡在登录凭据上。

---

### 3. X 搜索限读解除后验证

**状态**：@Quriov 被 X 临时限读（搜索 404，发推仍正常）。
**下一步**：
- 等几天自然恢复后，跑 `python scripts/search_x.py "smart glasses" --count 10` 验证恢复。
- **同时**：配一个小号专门用来搜索（`python scripts/set_cookie.py --role search --from-firefox`），以后搜索不用品牌号，彻底避免这个问题重演。

---

### 4. "内容来源自动生成"那层

**状态**：暂缓，用户还没想清楚。
**背景**：当前工具是"给它内容就发"。下一层是"AI 根据调研结果自动生成发布内容，再发出去"，形成调研 → 生成 → 发布的完整闭环。
**接续建议**：
- 明确"发什么内容、发到哪、针对谁"的策略。
- 再考虑加一个"内容生成"层（可以是一个新 skill，或在现有 skill 里加 `--auto-generate` 模式）。

---

### 5. Codex 成员同步链路验证

**状态**：已知 backlog，未验证。
**背景**：`sync-codex-skills.sh` 理论上能把 skill 同步给 Codex 成员，但 Codex 端从未实际跑通验证过。
**下一步**：跑一次 `sync-codex-skills.sh`，确认同步到 `~/.codex/skills/` 的内容是否能被 Codex 正确加载使用。如果不通，记录为待办、降级为"CC 端先用，Codex 共享后续再做"。

---

## 二、运维事项（持续需要关注的）

### X cookie 失效处理

**频率**：不定期，X cookie 会自然过期。
**处理方式**：
- 搜索 cookie 过期：在本机 Firefox 登录要用来搜的账号，跑 `python scripts/set_cookie.py --role search --from-firefox`，重新同步到服务器。
- 发布 cookie 过期：同上，`--role publish`。
- 注意：操作 `C:\QuriovXTools\cookies\`，不要碰 `C:\AIInfoHub\data\cookies.json`（那是日报管线的）。

### twikit 补丁维护

X 的反爬机制会持续更新，twikit 补丁可能需要跟进。如果搜索/发推突然失败且报 `KEY_BYTE indices` 相关错误，需要更新 `patch_twikit.py`（重新分析 X 前端 JS 的字节索引逻辑）。

---

## 三、可能的后续扩展

| 方向 | 描述 | 难度估计 |
|------|------|---------|
| TikTok 读 | 调研 TikTok 评论 / 用户讨论 | 高（反爬严格，没有官方 API）|
| Reddit 发（账号问题解决后） | 低，代码已完整 | 低 |
| X 搜索更换小号 | 用 set_cookie 配好搜索专用小号，彻底和品牌号分开 | 很低 |
| YouTube 写操作扩展 | 给视频打评论回复、批量操作 | 中 |
| 发布内容自动生成 | 调研 → AI 生成内容 → 发布的完整闭环 | 中（需要明确策略）|
| Codex 共享链路 | 验证 sync-codex-skills.sh 的 Codex 端 | 未知 |
