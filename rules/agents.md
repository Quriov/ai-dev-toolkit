# Agent Orchestration

## Model Selection for Subagents

ALL implementation subagents MUST use Opus model (set via `model: "opus"` parameter).
The global env var `CLAUDE_CODE_SUBAGENT_MODEL=opus` is configured in settings.json.

DO NOT use Sonnet or Haiku for:
- Code implementation tasks
- Bug fixes
- Frontend/backend modifications
- Any task that writes or edits code

## Task Splitting Strategy

### When to split into MULTIPLE parallel agents:
- Tasks touch DIFFERENT files (no overlap)
- Tasks are logically independent
- Each task is self-contained (agent doesn't need output from another)

### When to use a SINGLE agent:
- Tasks modify the SAME file
- Tasks have sequential dependencies (task B needs task A's output)
- Task is small enough to complete in <5 minutes

### Optimal task size per agent:
- ONE clear objective (not 4+ unrelated fixes)
- 1-3 files to modify
- Clear success criteria
- Include verification step in the prompt

### MANDATORY: Post-completion verification
After ANY frontend change, ALWAYS run a verification step:
1. `npm run build` to catch TypeScript errors
2. Run relevant Playwright E2E tests to verify functionality
3. If visual changes (colors, layout), use browser automation to screenshot and verify

### Example: BAD vs GOOD task splitting

```
BAD (one agent, 4 unrelated tasks):
  Agent: Fix colors + add columns + change language + add auto-update

GOOD (parallel agents, focused tasks):
  Agent 1: Fix Handsontable cell colors (PricingReview.tsx only)
  Agent 2: Add auto exchange rate update (backend/app/main.py only)
  Agent 3: Convert UI to Chinese-only (i18n files + Layout)
  Verification Agent: Screenshot all pages, report issues
```

## Available Agents

Located in `~/.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Implementation planning | Complex features, refactoring |
| architect | System design | Architectural decisions |
| tdd-guide | Test-driven development | New features, bug fixes |
| code-reviewer | Code review | After writing code |
| security-reviewer | Security analysis | Before commits |
| build-error-resolver | Fix build errors | When build fails |
| e2e-runner | E2E testing | Critical user flows |
| refactor-cleaner | Dead code cleanup | Code maintenance |
| doc-updater | Documentation | Updating docs |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests - Use **planner** agent
2. Code just written/modified - Use **code-reviewer** agent
3. Bug fix or new feature - Use **tdd-guide** agent
4. Architectural decision - Use **architect** agent

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations.

## Parallel Subagent Strategy (MANDATORY)

收到任务后, 必须先判断是否可以拆分并行. 不要串行做完一个再做下一个.

### 决策流程

收到任务 -> 列 todo -> 识别独立子任务 -> 立即并行 dispatch

### 何时必须拆分
- **调研+修复**: 探索阶段一个 agent, 不等探索完就把已知的独立调研任务分出去
- **多文件修改**: 不同文件的改动拆给不同 agent (如 frontend + backend 同时改)
- **测试+修复并行**: 修复代码的同时让另一个 agent 扩展测试脚本
- **多页面浏览器验证**: 每个页面一个 agent (用不同 session name)
- **主线任务+杂务**: 环境问题/工具问题等丢给后台 agent, 主线不中断
- **信息收集**: 需要查多个来源时, 每个来源一个 agent

### 执行原则
- 拆分后立即 dispatch, 不要"先做完这个再拆"
- 后台 agent (`run_in_background: true`) 用于不阻塞主线的任务
- 前台 agent 用于需要结果才能继续的任务
- 汇总结果时统一处理, 不逐个等待
- 每个 agent prompt 要自包含 (包含所有必要上下文), 不要假设 agent 知道当前对话内容

## Multi-Perspective Analysis

For complex problems, use split role sub-agents:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker
