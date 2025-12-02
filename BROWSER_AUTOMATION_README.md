# AWS Browser Automation Integration

This integration adds web search, scraping, and screenshot capabilities to your Claude agent using AWS Browser Automation and Playwright.

## Architecture

The integration uses AgentCore's BrowserClient directly for browser automation:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: agent.py                                           │
│ - Registers browser tools directly                          │
│ - Exposes tools to Claude: search_web, scrape_page,         │
│   take_screenshot                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: browser_utils.py                                   │
│ - BrowserManager using browser_session context manager      │
│ - Wraps bedrock_agentcore BrowserClient                     │
│ - Provides methods: search_web(), scrape_page(),            │
│   take_screenshot()                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ bedrock_agentcore.tools.browser_client                      │
│ - browser_session context manager                           │
│ - BrowserClient for session management                      │
│ - Automatic WebSocket URL and header generation             │
└─────────────────────────────────────────────────────────────┘
                          ↓
                 AWS Browser Automation
```

## Setup

### 1. Install Dependencies

```bash
pip install playwright
playwright install chromium
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure AWS region:

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# AWS Configuration
AWS_REGION=us-east-1

# Optional: Claude Model Configuration
CLAUDE_CODE_USE_BEDROCK=1
```

**Note:** AWS credentials should be configured via standard AWS credential chain (AWS CLI, environment variables, or IAM roles). AgentCore automatically manages browser tool IDs and resources.

## Available Tools

### 1. `search_web`

Navigate to a URL and perform web searches by filling forms and clicking buttons.

**Parameters:**
- `url` (str): URL to navigate to
- `search_query` (str, optional): Text to search for
- `search_selector` (str, optional): CSS selector for search input
- `submit_button` (str, optional): CSS selector for submit button
- `wait_selector` (str, optional): CSS selector to wait for after search
- `take_screenshot` (bool, optional): Whether to capture screenshot

**Example:**
```python
{
    "url": "https://www.amazon.com",
    "search_query": "laptop",
    "search_selector": "input#twotabsearchtextbox",
    "wait_selector": "div.s-main-slot",
    "take_screenshot": True
}
```

### 2. `scrape_page`

Extract content from web pages using CSS selectors.

**Parameters:**
- `url` (str, optional): URL to scrape (if None, uses current page)
- `selectors` (list, optional): CSS selectors to extract
- `extract_text` (bool): Extract text content (default: True)
- `extract_html` (bool): Extract HTML content (default: False)

**Example:**
```python
{
    "url": "https://example.com",
    "selectors": ["h1", ".price", "#description"],
    "extract_text": True,
    "extract_html": False
}
```

### 3. `take_screenshot`

Capture screenshots of web pages.

**Parameters:**
- `url` (str, optional): URL to screenshot (if None, uses current page)
- `full_page` (bool): Capture full scrollable page (default: False)
- `selector` (str, optional): CSS selector of element to screenshot

**Example:**
```python
{
    "url": "https://example.com",
    "full_page": True
}
```

## Testing

### Direct Client Testing

Test the browser automation client directly without the agent:

```bash
python test_scripts/test_browser_automation.py
```

This will:
1. Search Amazon for "laptop"
2. Scrape example.com
3. Take screenshots
4. Save screenshots as PNG files

### Agent Testing

Test browser automation through the Claude agent:

```bash
# Update agent_arn in test_browser_via_agent.py first
python test_scripts/test_browser_via_agent.py
```

## Usage Examples

### Example 1: Search and Extract

```python
prompt = """
Search Google for "AWS Bedrock" and extract the top 5 result titles and URLs.
"""
```

Claude will:
1. Use `search_web` to navigate to Google
2. Fill in the search query
3. Use `scrape_page` to extract results

### Example 2: Price Monitoring

```python
prompt = """
Go to amazon.com and search for "MacBook Pro".
Extract the prices of the first 5 results.
"""
```

### Example 3: Visual Verification

```python
prompt = """
Take a screenshot of anthropic.com and tell me what you see.
"""
```

Claude will use `take_screenshot` and analyze the image.

## How It Works

### 1. Connection Flow

```python
# Uses AgentCore's browser_session context manager
from bedrock_agentcore.tools.browser_client import browser_session

with browser_session('us-east-1') as client:
    # Generate WebSocket URL and authentication headers
    ws_url, headers = client.generate_ws_headers()

    # Playwright connects via CDP
    browser = playwright.chromium.connect_over_cdp(ws_url, headers=headers)
    page = browser.contexts[0].pages[0]
```

### 2. Session Management

- Each operation uses browser_session context manager
- Session cleanup is automatic (handled by context manager)
- No manual presigned URL management required
- BrowserClient handles session lifecycle

### 3. Data Flow

```
User Prompt
    ↓
Claude decides to use browser tool
    ↓
Tool function receives call
    ↓
BrowserManager executes via browser_session
    ↓
Playwright commands via WebSocket
    ↓
AWS Browser Automation performs action
    ↓
Result returned to Claude
    ↓
Claude interprets and responds
```

## Response Format

All browser automation tools return a `BrowserAutomationResult`:

```json
{
  "success": true,
  "session_id": "abc123...",
  "execution_time": 2.34,
  "output": "Title: Example Domain\nURL: https://example.com\n...",
  "screenshot_base64": "iVBORw0KGgo...",
  "scraped_content": {
    "title": "Example Domain",
    "url": "https://example.com",
    "text": "Example Domain...",
    "elements": [...]
  },
  "error": null
}
```

## Troubleshooting

### Error: "Failed to connect to browser"

**Possible causes:**
1. AWS credentials not configured
2. Network connectivity issues
3. Playwright not installed
4. Missing bedrock-agentcore package

**Solution:**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Reinstall Playwright
pip install playwright
playwright install chromium
```

### Error: "Session timeout"

**Solution:** Browser sessions have a timeout (default 900s). Reconnection happens automatically.

### Screenshots not saving

**Solution:** Ensure write permissions in the current directory:
```bash
chmod +w .
```

## Best Practices

1. **Reuse connections**: The client maintains a connection across multiple operations
2. **Use specific selectors**: Be as specific as possible with CSS selectors
3. **Add wait conditions**: Use `wait_selector` to ensure content loads
4. **Handle errors gracefully**: Check `result.success` before using data
5. **Clean up**: Use context manager or call `client.close()` when done

## Comparison with Code Interpreter

| Feature | Code Interpreter | Browser Automation |
|---------|------------------|-------------------|
| **Purpose** | Execute Python/bash code | Web scraping, automation |
| **Session Type** | Stateful (session ID) | Connection-based |
| **Tools** | 4 tools (execute, write, read, command) | 3 tools (search, scrape, screenshot) |
| **Output** | Text, files | Text, HTML, images (base64) |
| **Use Cases** | Data analysis, file processing | Web research, monitoring |

## Security Considerations

1. **Credentials**: Never hardcode credentials; use environment variables
2. **URL validation**: Be cautious with user-provided URLs
3. **Data sanitization**: Sanitize scraped content before processing
4. **Rate limiting**: Respect website terms of service and rate limits
5. **Session cleanup**: Always close browser connections when done

## Integration with Existing Agent

The browser automation tools work seamlessly with existing code interpreter tools:

```python
prompt = """
1. Search Amazon for "laptop"
2. Scrape the prices
3. Use Python to calculate the average price
4. Generate a chart
"""
```

Claude will:
1. Use `search_web` to search Amazon
2. Use `scrape_page` to extract prices
3. Use `mcp__codeint__execute_code` to analyze data
4. Use `mcp__codeint__write_files` to save chart

## Next Steps

- [ ] Add authentication support for logged-in sites
- [ ] Implement cookie management
- [ ] Add proxy support
- [ ] Create more specialized tools (form filling, file downloads)
- [ ] Add retry logic for flaky selectors

## Resources

- [AWS Browser Automation Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/browser-automation.html)
- [Playwright Documentation](https://playwright.dev/python/)
- [Claude Agent SDK](https://github.com/anthropics/anthropic-sdk-python)
