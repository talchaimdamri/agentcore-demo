# Changelog

## [1.2.0] - AgentCore Invoke UI

### Added

#### Web-based Invoke UI (`agentcore-ui/`)
- `api.py` - FastAPI backend with SSE streaming endpoint
  - boto3 integration for agent invocation
  - Session ID extraction from response metadata
  - CORS enabled for local development
- `index.html` - Premium dark-themed frontend
  - JetBrains Mono + Instrument Sans typography
  - Amber/gold accent color scheme
  - Real-time streaming chat interface
  - Session management with dropdown selector
  - In-memory message persistence across session switches
  - Typing indicator with animated dots
  - Tool usage badges
- `invoke.html` - Simple minimal frontend (original version)

#### Dependencies
- Added `fastapi` and `uvicorn[standard]` for the backend server

### Modified

#### agent.py
- Changed default model from Claude Sonnet 4.5 to Claude Haiku 4.5
  - `global.anthropic.claude-haiku-4-5-20251001-v1:0` (Bedrock)
  - `claude-haiku-4-5-20251001` (Anthropic API)

---

## [1.1.0] - S3 Storage Integration

### Added

#### S3 Storage Tools
- `upload_to_s3` - Upload files from Code Interpreter to S3 bucket
- `download_from_s3` - Download files from S3 to Code Interpreter
- `list_s3_files` - List files in S3 bucket with optional prefix filter

### Modified

#### code_int_mcp/server.py
- Added 3 new S3 storage MCP tools
- Updated tools registration to include S3 tools

#### code_int_mcp/client.py
- Updated code interpreter identifier to S3-enabled version (`s3_code_interpreter-Eb7yoYoic6`)

#### agent.py
- Added S3 tools to allowed tools list
- Added S3 tools documentation to system prompt

---

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
