# Claude Code Best Practices Reference

Comprehensive reference for Claude Code features and patterns. Use this to inform recommendations during conversation analysis.

## Table of Contents

1. [Foundational Principles](#foundational-principles)
2. [CLAUDE.md Configuration](#claudemd-configuration)
3. [Hooks System](#hooks-system)
4. [Skills](#skills)
5. [Subagents](#subagents)
6. [Model Context Protocol (MCP)](#model-context-protocol-mcp)
7. [Dev Docs System](#dev-docs-system)
8. [Core Workflows](#core-workflows)

---

## Foundational Principles

### Collaborative Mindset
- Treat Claude as a brilliant junior developer needing senior guidance
- Engage in planning, reviewing, and iterating together
- Stop "vibe-coding" and expecting magical outputs

### Embrace Specificity
Claude's success rate is proportional to instruction clarity:

| Poor | Good |
|------|------|
| add tests for foo.py | write a new test case for foo.py, covering the edge case where the user is logged out. avoid mocks |
| why does ExecutionFactory have such a weird api? | look through ExecutionFactory's git history and summarize how its api came to be |

### When to Intervene Manually
If Claude struggles for 30 minutes on something you could fix in 2, step in. This is collaborative, not a defeat.

### Reflective Prompting
When Claude produces suboptimal output, ask: "How could my prompt have been better?" Use double-escape to revisit and rephrase prompts.

---

## CLAUDE.md Configuration

### Purpose
Automatically inject persistent, project-specific context at session start.

### Effective CLAUDE.md Contains
- **Common Commands**: `npm run build`, `pnpm pm2:start`
- **Code Style**: Syntax, branch naming, merge strategies
- **Testing Instructions**: How to run tests, authenticated routes
- **Project Quirks**: Unexpected behaviors, environment setup notes

### Location Hierarchy
1. **Repository Root**: Team-wide standards, checked into version control
2. **Parent/Child Directories**: Monorepo support, global + service-specific
3. **Home Folder** (`~/.claude/CLAUDE.md`): Global personal context

### Best Practices
- Use `#` key to instantly add instructions to CLAUDE.md
- Periodically run CLAUDE.md through a prompt improver
- Use emphasis words: "IMPORTANT", "YOU MUST", "NEVER"

---

## Hooks System

### Pre-Prompt Hook (UserPromptSubmit)

Executes before Claude processes a prompt. Use for:
- Validating environment state
- Forcing skill consideration
- Injecting context based on keywords

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "match": "build|deploy|compile",
      "command": "node scripts/validate_environment.js"
    }]
  }
}
```

### Post-Response Hooks (Stop Event)

Triggers after Claude finishes. Use for:
- **File Edit Tracker**: Log modified repositories
- **Build Checker**: Run build scripts on affected repos
- **Error Handling Reminder**: Analyze for risky patterns

```json
{
  "hooks": {
    "Stop": [{
      "command": "node scripts/post_response_checks.js"
    }]
  }
}
```

### Skill-Triggering Hook Architecture

```json
// skill-rules.json
{
  "pdf-editor": {
    "keywords": ["pdf", "rotate", "merge"],
    "file_patterns": ["*.pdf"]
  }
}
```

Pre-prompt hook reads this config and injects directives to force skill consideration.

---

## Skills

### What They Are
Reusable folders containing instructions, scripts, and resources for domain expertise.

### When to Use
- **Organizational Workflows**: Brand guidelines, compliance, templates
- **Domain Expertise**: Data analysis, code review standards, PDF manipulation
- **Personal Preferences**: Coding patterns, research methods

### Token-Efficient Design
Skills use "progressive disclosure":
1. Only metadata loads initially (~100 words)
2. Full SKILL.md loads when triggered (<5k words)
3. Bundled resources load as needed (unlimited)

### Skill Structure
```
skill-name/
├── SKILL.md           # Instructions + frontmatter
├── scripts/           # Executable code
├── references/        # Documentation
└── assets/            # Templates, images
```

### When to Graduate a Prompt to a Skill
If you type the same complex prompt repeatedly across sessions, convert it to a skill.

---

## Subagents

### What They Are
Specialized, independent AI assistants with isolated context windows and custom permissions.

### When to Use
- **Task Specialization**: Code review, test generation, security audits
- **Context Management**: Offload work, preserve main context window
- **Parallel Processing**: Multiple agents on different aspects

### Configuration Example
```json
{
  "subagents": {
    "code-reviewer": {
      "tools": ["Read", "Grep", "Glob"],
      "system_prompt": "Review code for quality and security. No write access."
    },
    "test-generator": {
      "tools": ["Read", "Write", "Bash"],
      "system_prompt": "Generate comprehensive tests following TDD."
    }
  }
}
```

### Best Practice: Read-Only Review Agent
Configure with Read, Grep, Glob but NO write permissions for safe parallel review.

---

## Model Context Protocol (MCP)

### What It Is
Open standard connecting AI agents to external systems (databases, CRMs, Google Drive).

### When to Use
- Accessing database schemas without copy-paste
- Querying external APIs during development
- Connecting to business tools (CRMs, issue trackers)

### Configuration
```json
{
  "mcpServers": {
    "postgres": {
      "command": "mcp-postgres",
      "args": ["--connection-string", "$DATABASE_URL"]
    },
    "github": {
      "command": "mcp-github",
      "args": ["--token", "$GITHUB_TOKEN"]
    }
  }
}
```

### Skills vs MCP
- **MCP**: Provides the connection (tool connectivity)
- **Skills**: Teaches what to do with the data (procedural knowledge)

---

## Dev Docs System

### The Problem
Multi-session projects suffer "context amnesia" - Claude loses the plot.

### The Solution
External memory via task-specific documentation:

```
dev/active/[task-name]/
├── plan.md      # Accepted implementation plan
├── context.md   # Key files, architectural decisions
└── tasks.md     # Remaining work checklist
```

### How to Use
1. Instruct Claude to read files when continuing tasks
2. Update files as steps complete
3. Files survive session ends and context compactions

### When to Recommend
- Projects spanning 3+ sessions
- Multiple context compactions observed
- High error rates from lost context

---

## Core Workflows

### Explore, Plan, Code, Commit
1. **Explore**: Read files, images, URLs - NO CODE YET
2. **Plan**: Create implementation plan. Use "ultrathink" for complex problems
3. **Code**: Implement the approved plan
4. **Commit**: Git commit, PR, update docs

### Test-Driven Development (TDD)
1. Write tests based on expected inputs/outputs
2. Run tests - confirm they fail
3. Commit failing tests
4. Implement code to make tests pass (NO modifying tests)

### Codebase Onboarding
Use Claude as interactive guide:
- "How does logging work?"
- "How do I make a new API endpoint?"
- "What edge cases does CustomerOnboardingFlowImpl handle?"

### Git/GitHub Automation
With `gh` CLI installed:
- Create PRs from code review comments
- Resolve failing CI builds
- Triage open issues
- Search git history for design decisions

---

## Tool Comparison Quick Reference

| Feature | Skills | Subagents | MCP | CLAUDE.md | Hooks |
|---------|--------|-----------|-----|-----------|-------|
| **Purpose** | Procedural knowledge | Task delegation | Tool connectivity | Background context | Event triggers |
| **Persistence** | Across conversations | Across sessions | Continuous | Session start | Per event |
| **Best For** | Complex procedures | Parallel work | Data access | Project basics | Automation |
