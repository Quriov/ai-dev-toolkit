#!/usr/bin/env node

/**
 * Dev Loop Verification Hook (Stop event)
 *
 * Checks three things after every Claude response:
 * 1. Completion claims without test evidence → warns to run tests
 * 2. High error rate in Bash commands → suggests retrospective
 * 3. User corrections detected → suggests retrospective
 *
 * Reads hook JSON from stdin (Claude Code Stop hook protocol).
 * Outputs warning text to stdout if issues found (empty = no warning).
 */

const { readFileSync } = require('fs');
const { join } = require('path');

let input = '';
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const hookData = JSON.parse(input);
    const messages = hookData.messages || [];
    if (messages.length === 0) return;

    // Only check test evidence if the project has test infrastructure
    const cwd = hookData.cwd || process.cwd();
    const hasTestInfra = ['package.json', 'pytest.ini', 'pyproject.toml', 'Makefile']
      .some(f => {
        try {
          const content = readFileSync(join(cwd, f), 'utf8');
          return /test:check|pytest|test:/.test(content);
        } catch { return false; }
      });

    const warnings = [];

    // --- Check 1: Completion claim without test evidence ---
    const lastAssistant = messages.filter(m => m.role === 'assistant').pop();
    if (lastAssistant && hasTestInfra) {
      const text = typeof lastAssistant.content === 'string'
        ? lastAssistant.content
        : Array.isArray(lastAssistant.content)
          ? lastAssistant.content.map(b => b.text || '').join(' ')
          : '';

      const completionPatterns = [
        /\b(完成|修复|已修|搞定|done|fixed|complete|resolved)\b/i,
        /all\s+pass/i, /全部通过/, /0\s*(failed|失败)/,
      ];

      if (completionPatterns.some(p => p.test(text))) {
        const recentTools = messages
          .filter(m => m.role === 'assistant').slice(-5)
          .flatMap(m => {
            if (!Array.isArray(m.content)) return [];
            return m.content.filter(b => b.type === 'tool_use')
              .map(b => JSON.stringify(b.input || {}));
          });

        const hasTestEvidence = recentTools.some(t =>
          /test:check|playwright test|pytest|npm run test|verify_visual/i.test(t)
        );

        if (!hasTestEvidence) {
          warnings.push(
            '[DEV-LOOP] You claimed completion but no test evidence in recent tool calls. ' +
            'Run test:check before reporting.'
          );
        }
      }
    }

    // --- Check 2: High Bash error rate → suggest retrospective ---
    // Count Bash tool_use results with non-zero exit codes or error patterns
    let bashTotal = 0;
    let bashErrors = 0;

    for (const msg of messages) {
      if (msg.role !== 'tool') continue;
      const content = typeof msg.content === 'string' ? msg.content
        : Array.isArray(msg.content) ? msg.content.map(b => b.text || '').join(' ') : '';

      // Heuristic: tool results containing error indicators
      if (content.length > 0) {
        bashTotal++;
        if (/Exit code [1-9]|Error:|FAILED|error\[E|Cannot find|ModuleNotFoundError|SyntaxError/i.test(content)) {
          bashErrors++;
        }
      }
    }

    if (bashTotal >= 5 && bashErrors / bashTotal > 0.4) {
      warnings.push(
        `[RETRO] High error rate: ${bashErrors}/${bashTotal} commands failed (${Math.round(bashErrors/bashTotal*100)}%). ` +
        'Consider pausing to diagnose the root cause before continuing. ' +
        'If this was a multi-step fix, update .claude/playbook.md with the pattern.'
      );
    }

    // --- Check 3: User corrections (secondary signal) ---
    const userMessages = messages.filter(m => m.role === 'user').slice(-15);
    const correctionPatterns = [
      /没有解决|没解决|不对|不行|还是|仍然|still|not working|wrong|broken/i,
      /问题仍|bug still|没修好|没生效/i,
    ];

    let correctionCount = 0;
    for (const msg of userMessages) {
      const text = typeof msg.content === 'string' ? msg.content
        : Array.isArray(msg.content) ? msg.content.map(b => b.text || '').join(' ') : '';
      if (correctionPatterns.some(p => p.test(text))) correctionCount++;
    }

    if (correctionCount >= 3) {
      warnings.push(
        `[RETRO] ${correctionCount} correction signals detected. ` +
        'Pause and retrospect: what is the root cause? Update .claude/playbook.md.'
      );
    }

    // --- Check 4: Scope amnesia — user listed multiple requirements but "done" claimed ---
    // Detect if user's last long message had numbered items and completion was claimed
    if (claimsCompletion) {
      const lastLongUserMsg = userMessages.reverse().find(msg => {
        const text = typeof msg.content === 'string' ? msg.content
          : Array.isArray(msg.content) ? msg.content.map(b => b.text || '').join(' ') : '';
        // Check if message has numbered items (第一...第二... or 1. 2. 3.)
        return (text.match(/第[一二三四五六七八九十]|[1-9]\./g) || []).length >= 3;
      });
      if (lastLongUserMsg) {
        warnings.push(
          '[SCOPE-CHECK] The user listed multiple numbered requirements. ' +
          'Re-read their original message and verify EACH point is addressed before reporting done.'
        );
      }
    }

    if (warnings.length > 0) {
      console.log(warnings.join('\n'));
    }
  } catch {
    // Silent fail -- don't block Claude responses
  }
});
