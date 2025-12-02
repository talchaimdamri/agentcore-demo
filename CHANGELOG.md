# Changelog

## [1.0.0] - Based on AWS Sample

This project is a fork of the [AWS Claude Agent with Code Interpreter](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/03-integrations/agentic-frameworks/claude-agent/claude-with-code-interpreter) example from [AWS Labs](https://github.com/awslabs/amazon-bedrock-agentcore-samples).

### Added

#### Browser Automation
- `browser_mcp/server.py` - MCP server with 3 browser tools:
  - `search_web` - Navigate URLs, fill forms, click buttons
  - `scrape_page` - Extract content via CSS selectors
  - `take_screenshot` - Capture page screenshots
- `browser_utils.py` - BrowserManager class wrapping Playwright + AgentCore BrowserClient
- `browser-policy.json` - Browser security policy
- `BROWSER_AUTOMATION_README.md` - Comprehensive documentation (339 lines)

#### Claude Skills Integration
- `.claude/skills/` - Skills directory structure
- Skills path discovery and logging in agent.py
- `setting_sources=["user", "project"]` configuration for loading Skills

#### Utility Scripts
- `download_presentation.py` - Download files from Code Interpreter sessions
- `download_session_files.py` - Interactive session file browser with menu
- `create_cats_presentation_locally.py` - Local PPTX creation example
- `get_presentation_base64.py` - Base64 encoding utility

#### Configuration
- `.env.example` - Environment variable template
- `.gitignore` - Custom gitignore for the project

#### Dependencies
- Added `playwright>=1.40.0` for browser automation

### Modified

#### agent.py - Major Enhancements

| Feature | Original | This Version |
|---------|----------|--------------|
| MCP Servers | 1 (codeint) | 2 (codeint + browser) |
| Allowed Tools | 4 | 8 + Skills |
| Model Selection | Hardcoded | Dynamic via `CLAUDE_CODE_USE_BEDROCK` env var |
| Skills Support | None | Full (cwd, setting_sources) |
| Error Handling | Basic (crashes on bad JSON) | Robust (try/except with logging) |
| System Prompt | Code interpreter only | Code interpreter + Browser automation |

Key changes:
- **Dynamic Model Selection** - Choose between Bedrock and Anthropic API via environment variable
- **Browser MCP Server** - Added second MCP server for web automation
- **Skills Support** - Added `cwd`, `setting_sources`, and `Skill` tool for Claude Code Skills
- **Expanded Tools** - From 4 to 8 tools plus Skills capability
- **Enhanced System Prompt** - Added comprehensive browser automation tool documentation
- **Robust Error Handling** - try/except for JSON parsing in agentic loop (prevents crashes on malformed responses)

#### pyproject.toml
- Added `playwright>=1.40.0` dependency for browser automation
