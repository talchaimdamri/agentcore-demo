from code_int_mcp.server import code_int_mcp_server
from browser_mcp.server import browser_mcp_server
from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ResultMessage,
    ClaudeAgentOptions,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKClient,
    ToolResultBlock,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging
import json
import os

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def main(payload):
    """
    Entrypoint to the agent. Takes the user prompt, uses code interpreter tools to execute the prompt.
    Yields intermediate responses for streaming.
    """
    prompt = payload["prompt"]
    session_id = payload.get("session_id", "")
    agent_responses = []
    code_int_session_id = session_id

    # Determine model format based on CLAUDE_CODE_USE_BEDROCK environment variable
    use_bedrock = os.environ.get("CLAUDE_CODE_USE_BEDROCK", "1") == "1"
    model_name = (
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0"
        if use_bedrock
        else "claude-sonnet-4-5-20250929"
    )
    logger.info(f"Using {'Bedrock' if use_bedrock else 'Anthropic API'} with model: {model_name}")

    # Log current working directory and Skills path for debugging
    current_dir = os.getcwd()
    skills_path = os.path.join(current_dir, ".claude", "skills")
    logger.info(f"Current working directory: {current_dir}")
    logger.info(f"Looking for Skills at: {skills_path}")
    if os.path.exists(skills_path):
        logger.info(f"Skills directory exists with: {os.listdir(skills_path)}")
    else:
        logger.warning(f"Skills directory not found at: {skills_path}")

    options = ClaudeAgentOptions(
        mcp_servers={
            "codeint": code_int_mcp_server,
            "browser": browser_mcp_server,
        },
        model=model_name,
        cwd=os.getcwd(),  # Explicitly set working directory for Skills discovery
        setting_sources=["user", "project"],  # Enable loading Skills from filesystem
        allowed_tools=[
            "Skill",  # Enable Skills
            "mcp__codeint__execute_code",
            "mcp__codeint__execute_command",
            "mcp__codeint__write_files",
            "mcp__codeint__read_files",
            "mcp__browser__search_web",
            "mcp__browser__scrape_page",
            "mcp__browser__take_screenshot",
        ],
        system_prompt=f"""You are an AI assistant that helps users with tasks associated with code generation, execution, and web automation.

  CRITICAL RULES:
  1. You MUST use mcp__codeint__execute_code for ALL Python code execution tasks. If a library is not found, rewrite code to use an alternate library. Do not attempt to install missing libraries.
  2. You can use mcp__codeint__execute_command to execute bash commands within code interpreter session.
  3. You can use mcp__codeint_write_files to write/save files within code interpreter session.
  4. Use the tools without asking for permission
  5. Use the {code_int_session_id} when invoking code interpreter tools to continue the session. Do not make it as 'default. Pass it even if its empty.

  CODE INTERPRETER TOOLS:
  - mcp__codeint__execute_code: Execute Python/code snippets.
  - mcp__codeint__execute_command: Execute bash/shell commands
  - mcp__codeint_write_files: Write/save files. Make a list of path - name of the file, text - contents of the file
  - mcp__codeint_read_files: Read files. Make a list of path - name of the file

  BROWSER AUTOMATION TOOLS (AgentCore BrowserClient):
  - mcp__browser__search_web: Navigate to URLs and perform web searches
    * Use for: Searching websites, filling forms, clicking buttons
    * Parameters: url, search_query, search_selector, submit_button, wait_selector, take_screenshot
    * Example: Search Amazon for "laptop" using selector "input#twotabsearchtextbox"

  - mcp__browser__scrape_page: Extract content from web pages
    * Use for: Getting text, HTML, or specific elements via CSS selectors
    * Parameters: url, selectors (list), extract_text, extract_html
    * Example: Extract all h1 tags and prices from a product page

  - mcp__browser__take_screenshot: Capture screenshots of web pages
    * Use for: Visual documentation, debugging, monitoring
    * Parameters: url, full_page, selector
    * Returns: Base64-encoded screenshot

  Your response should:
  1. Show the results
  2. Provide a brief explanation
  """,
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        logger.info("*" * 80 + "\n")
                        logger.info("TOOL USE: %s", block.name)
                        logger.info(
                            "Input Parameters:\n%s", json.dumps(block.input, indent=2)
                        )
                        logger.info("*" * 80 + "\n")
                        # Yield tool use as a streaming chunk
                        yield {
                            "type": "tool_use",
                            "tool_name": block.name,
                            "tool_input": block.input,
                            "session_id": code_int_session_id,
                        }
                    elif isinstance(block, TextBlock):
                        logger.info("*" * 80 + "\n")
                        logger.info("Agent response: %s", block.text)
                        logger.info("*" * 80 + "\n")
                        agent_responses.append(block.text)
                        # Yield text response as a streaming chunk
                        yield {
                            "type": "text",
                            "text": block.text,
                            "session_id": code_int_session_id,
                        }
            elif isinstance(msg, UserMessage):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        if block.content and len(block.content) > 0:
                            if isinstance(block.content[0], dict):
                                text_content = block.content[0].get("text", "")
                                logger.info("*" * 80 + "\n")
                                logger.info("Tool Result: %s", text_content)
                                logger.info("*" * 80 + "\n")
                                # Parse tool result and extract session ID if available
                                # This allows the agent to continue even if parsing fails
                                try:
                                    result_data = json.loads(text_content)
                                    extracted_session_id = result_data.get(
                                        "code_int_session_id", ""
                                    )
                                    if extracted_session_id:
                                        code_int_session_id = extracted_session_id
                                except json.JSONDecodeError as e:
                                    logger.warning("Failed to parse tool result JSON: %s", e)
                                    logger.warning("Raw content: %s", text_content[:200])
                                    # Continue the loop - let Claude see the error and retry
                        logger.info("*" * 80 + "\n")
            elif isinstance(msg, ResultMessage):
                logger.info("*" * 80 + "\n")
                logger.info("ResultMessage received - conversation complete %s", msg)
                break  # Exit loop when final result is received

    # Yield final response with complete data
    yield {
        "type": "final",
        "response": "\n".join(agent_responses)
        if agent_responses
        else "No response from agent",
        "session_id": code_int_session_id,
    }


if __name__ == "__main__":
    app.run()
