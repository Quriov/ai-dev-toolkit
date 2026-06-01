# AI Dev Toolkit

AI + 人类协作开发的工具包，包含 Claude Code 的 rules、hooks 和 skills。

基于 Quriov 团队在 TikTok 美区电商数据管理系统的实战经验提炼。

## 快速安装

```bash
git clone https://github.com/Quriov/ai-dev-toolkit.git
cd ai-dev-toolkit
bash install.sh
```

或让 Claude Code 自动安装：
```
读取 https://github.com/Quriov/ai-dev-toolkit 仓库的 README，按照说明安装所有 rules、hooks 和 commands 到我的 Claude Code 环境
```

## 三套核心体系

### 1. AI 闭环测试
确保 AI 写的每个功能都真正可用，而不仅仅是代码存在。
- Rules: `rules/ai-dev-loop.md`
- Hook: `hooks/dev-loop-check.js` (Stop 事件自动检查)

### 2. 深层意图分析
用户说的是表面需求，AI 需要找到深层目标并提出更好的方案。
- 三层框架: Layer 1 (表面需求) -> Layer 2 (直接目的) -> Layer 3 (深层目标)

### 3. 复盘迭代优化
每次多步骤任务完成后，提取教训并固化。
- Skill: `/retro` (调用执行完整复盘流程)

### 4. Skills 沉淀
把可复用的调研/分析 SOP 沉淀为 Claude Code skills，自动加载到上下文。
- Skill: `skills/reddit-research/` — Reddit 深度调研工具集（Arctic Shift API + 备路径 + 痛点提取）

## 文件结构

```
rules/               Rules (每次对话自动加载)
  ai-dev-loop.md     开发闭环 + 复盘 + 反模式清单
  agents.md          Subagent 协作规则 + 并行策略
  coding-style.md    代码风格
  security.md        安全检查清单
  testing.md         测试覆盖要求
hooks/               程序化自动检查
  dev-loop-check.js  Stop hook: 完成声明+错误率+纠正轮次
commands/            Slash Commands (/command 手动触发)
  retro.md           /retro 复盘迭代优化
skills/              Skills (frontmatter description 自动加载)
  reddit-research/   Reddit 调研：Arctic Shift API + fallback chain + 痛点提取 SOP
    SKILL.md
docs/                团队文档
  ai-dev-playbook.md AI 协作开发完整手册
```

## 手动安装

```bash
cp rules/*.md ~/.claude/rules/common/
cp hooks/*.js ~/.claude/hooks/
cp commands/*.md ~/.claude/commands/
# Skills 是目录结构，需要递归复制
mkdir -p ~/.claude/skills
cp -r skills/*/ ~/.claude/skills/
```

在 `~/.claude/settings.json` 的 `hooks.Stop` 中添加：
```json
{"type": "command", "command": "node \"~/.claude/hooks/dev-loop-check.js\""}
```

## License

MIT
