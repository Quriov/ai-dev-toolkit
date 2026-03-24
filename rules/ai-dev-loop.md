# AI Collaborative Development Loop

## Core Loop

Every feature/fix follows this mandatory loop:

```
Plan -> Implement -> Self-Test -> Fix -> Verify -> Report
```

Claude MUST complete the full loop autonomously. Only escalate to user at:
- Architectural decisions that change system design
- Business logic ambiguity
- Test failures after 3 self-fix attempts

## Implementation Rules

### 1. Test Before Report

NEVER report "done" or "fixed" without test evidence. Required:
- `npm run test:check` (or project-equivalent) must PASS
- For visual changes: screenshot OR getComputedStyle verification
- For API changes: contract test assertions

### 2. Subagent Task Boundaries

When dispatching parallel subagents:
- ONE file = ONE owner. Never let two subagents modify the same file.
- Each subagent prompt MUST include: "Also update the corresponding test files"
- Provide a shared pattern guide when 2+ subagents do similar work
- Verify ALL subagent outputs compile before running tests

### 3. Test-Driven Development (TDD)

MANDATORY workflow for all features and bug fixes:
1. Write test first (RED) - test should FAIL
2. Write minimal implementation (GREEN) - test should PASS
3. Refactor (IMPROVE) - clean up while tests stay green
4. Run full suite to check for regressions
5. Verify coverage (80%+ target)

For bug fixes specifically:
- Write/update a test that reproduces the bug FIRST
- Verify the test FAILS before fixing

### 4. Per-Page Quick Verification

After changing a specific page, run only that page's tests first:
```bash
npm run test:page:<name>   # Fast feedback (~10s)
npm run test:check          # Full verification before reporting
```

### 5. Visual Verification Protocol

For CSS/styling changes:
- ALWAYS check `getComputedStyle()`, never `element.style`
- CSS specificity can silently override inline styles
- Take screenshots and save to project's verify_screenshots/
- Compare computed values against expected constants

### 6. Migration Pattern

When migrating components (e.g., library swap):
1. Create a MIGRATION_GUIDE.md with patterns BEFORE dispatching subagents
2. Include: selector conventions, component patterns, test update requirements
3. All subagents reference the same guide for consistency

## Retrospective

### When to Trigger

After any task that took 3+ correction rounds, multi-phase features, user-reported misses, or false-positive tests.

### Format

For each issue found:
```
### [Issue Title]
- **Symptom**: What the user saw / what failed
- **Root Cause**: Why it happened
- **Wasted Rounds**: How many extra cycles
- **Prevention**: Rule/tool/test added to prevent recurrence
- **Scope**: Project-specific or cross-project
```

### Where to Save

| Type | Location |
|------|----------|
| Behavioral rule | ~/.claude/rules/common/ |
| Project pattern | <project>/.claude/playbook.md |
| Test helper | tests/e2e/helpers/ |
| User preference | memory/feedback_*.md |

### Anti-Patterns to Watch For

1. **Report-before-verify**: Claiming "fixed" without running tests
2. **Surface-level check**: Checking DOM properties instead of computed/rendered state
3. **Serial where parallel**: Doing tasks sequentially when they could be parallelized
4. **Fix-the-test syndrome**: Changing test assertions to match broken behavior
5. **Duplicate work**: Main agent and subagent both doing the same search/fix
6. **Missing ownership**: Two subagents modifying the same file
7. **Todo replacement**: Completing tasks, then replacing the todo list with new tasks, losing pending items from earlier. ALWAYS check previous todo items are done before replacing the list.
8. **Scope creep amnesia**: User mentions 5 requirements, you implement 3, mark "done", forget the other 2. ALWAYS re-read the user's original message and check each point before reporting completion.
9. **Partial subagent delivery**: Subagent implements the "core" feature but skips "details" (e.g., build channel editing but skip grouping). The prompt must enumerate ALL deliverables explicitly.

### Completion Checklist (MANDATORY before reporting done)

Before saying "完成" or "done":
1. Re-read the user's ORIGINAL request message (scroll up if needed)
2. List each distinct requirement they mentioned
3. Check each one: implemented? tested? If not, add to todo and continue
4. Run test:check
5. **Functional interaction test**: For EACH new UI feature, write a Playwright script that USES the feature (click, type, submit), not just checks DOM existence. Test the happy path AND error path.
6. Only then report completion

### "Feature Exists" vs "Feature Works" Rule

A feature is NOT done until:
- It can be clicked/used without JS errors
- Its output is visible and correct
- Edge cases don't crash (null config, empty data, missing field)
- No `window.location.reload()` or other hacks to force refresh
- The feature is visually consistent with the rest of the UI (no English labels where Chinese expected, no duplicate UI elements)
