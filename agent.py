from code_int_mcp.server import code_int_mcp_server
from browser_mcp.server import browser_mcp_server
from claude_agent_sdk import (
    AgentDefinition,
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
from bedrock_agentcore.memory import MemorySessionManager
from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole
import logging
import json
import os
import re
import requests
from typing import List, Optional

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Episodic Memory Configuration (hardcoded)
EPISODIC_MEMORY_CONFIG = {
    "max_results_per_namespace": 3,    # top_k per search
    "total_max_results": 6,            # Hard cap on total episodic memories
    "min_relevance_score": 0.3,        # Threshold for inclusion
    "max_context_chars": 2000,         # Max characters in episodic context
}

# AgentCore Gateway Configuration
GATEWAY_CONFIG = {
    "url": "https://gateway-quick-start-7f81ff-semantic-v2iirm5b4e.gateway.bedrock-agentcore.eu-central-1.amazonaws.com/mcp",
    "token_endpoint": "https://my-domain-0fnrf9sj.auth.eu-central-1.amazoncognito.com/oauth2/token",
    "client_id": "5ggtr7ctfontos361o09he4qdd",
    "client_secret": "1hohqppda5ainap4a5068a168k0qhu08nqs183jhpgi02g5889dh",
}

# Global cache for gateway token
_gateway_token_cache = {"token": None, "expires_at": 0}


def get_gateway_auth_token() -> str:
    """
    Retrieve Bearer token for AgentCore Gateway via Cognito OAuth2 client_credentials flow.
    Caches the token until near expiry.
    """
    import time

    # Check cache first (with 60s buffer before expiry)
    if _gateway_token_cache["token"] and time.time() < _gateway_token_cache["expires_at"] - 60:
        logger.info("Using cached gateway token")
        return _gateway_token_cache["token"]

    try:
        response = requests.post(
            GATEWAY_CONFIG["token_endpoint"],
            data={
                "grant_type": "client_credentials",
                "client_id": GATEWAY_CONFIG["client_id"],
                "client_secret": GATEWAY_CONFIG["client_secret"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour

        # Update cache
        _gateway_token_cache["token"] = access_token
        _gateway_token_cache["expires_at"] = time.time() + expires_in

        logger.info(f"Gateway token obtained, expires in {expires_in}s")
        return access_token

    except requests.RequestException as e:
        logger.error(f"Failed to obtain gateway token: {e}")
        raise RuntimeError(f"Gateway authentication failed: {e}") from e


app = BedrockAgentCoreApp()

# Global cache for memory session manager
_memory_session_manager = None


def get_memory_session_manager() -> MemorySessionManager:
    """Lazy-initialize and cache the memory session manager."""
    global _memory_session_manager

    if _memory_session_manager is not None:
        return _memory_session_manager

    memory_id = os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID")
    if not memory_id:
        raise ValueError("BEDROCK_AGENTCORE_MEMORY_ID not set")

    _memory_session_manager = MemorySessionManager(
        memory_id=memory_id,
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )
    return _memory_session_manager


def get_stm_context(manager: MemorySessionManager, actor_id: str, session_id: str, k: int = 10) -> str:
    """Retrieve STM (conversation history) formatted for system prompt."""
    try:
        turns = manager.get_last_k_turns(actor_id=actor_id, session_id=session_id, k=k)
        if not turns:
            return ""

        history = []
        for turn in turns:
            for msg in turn:
                role = msg.get('role', 'unknown')
                text = msg.get('content', {}).get('text', '')
                if text:
                    label = "User" if role.lower() in ['user', 'human'] else "Assistant"
                    history.append(f"{label}: {text}")

        if not history:
            return ""

        return "\n## CONVERSATION HISTORY:\n" + "\n".join(history) + "\n"

    except Exception as e:
        logger.warning("Failed to get STM: %s", e)
        return ""


def get_semantic_strategy_id(manager: MemorySessionManager) -> Optional[str]:
    """Find the semantic strategy ID by listing memory records."""
    try:
        records = manager.list_long_term_memory_records(namespace_prefix="/", max_results=30)
        for rec in records:
            strategy_id = rec.get('memoryStrategyId', '')
            if 'semantic' in strategy_id.lower():
                return strategy_id
        return None
    except Exception as e:
        logger.warning("Failed to find semantic strategy: %s", e)
        return None


def get_ltm_context(manager: MemorySessionManager, actor_id: str, query: str, top_k: int = 5) -> str:
    """Search LTM (semantic memory) and format results for system prompt."""
    try:
        # First try to find semantic strategy and use proper namespace
        semantic_strategy_id = get_semantic_strategy_id(manager)

        if semantic_strategy_id:
            namespace = f"/strategies/{semantic_strategy_id}/actors/{actor_id}"
            logger.info(f"Using semantic strategy namespace: {namespace}")
        else:
            # Fallback to old namespace
            namespace = f"/users/{actor_id}/facts"
            logger.info(f"No semantic strategy found, using fallback namespace: {namespace}")

        memories = manager.search_long_term_memories(
            query=query,
            namespace_prefix=namespace,
            top_k=top_k
        )

        if not memories:
            return ""

        relevant = []
        for m in memories:
            text = m.get('content', {}).get('text', '')
            # API returns 'score', not 'relevanceScore'
            score = m.get('score', m.get('relevanceScore', 0))
            logger.info(f"LTM memory score: {score}, text preview: {text[:100] if text else 'empty'}")
            if text and score >= 0:
                relevant.append(f"- {text}")

        if not relevant:
            return ""

        return "\n## RELEVANT MEMORIES (Facts about user):\n" + "\n".join(relevant) + "\n"

    except Exception as e:
        logger.warning("Failed to search LTM: %s", e)
        return ""


def get_episodic_strategy_id(manager: MemorySessionManager) -> Optional[str]:
    """Find the episodic strategy ID by listing memory records and extracting strategy IDs."""
    try:
        records = manager.list_long_term_memory_records(namespace_prefix="/", max_results=20)
        for rec in records:
            strategy_id = rec.get('memoryStrategyId', '')
            if 'episodic' in strategy_id.lower():
                return strategy_id
        return None
    except Exception as e:
        logger.warning("Failed to find episodic strategy: %s", e)
        return None


def parse_episodic_content(content_text: str) -> dict:
    """Parse episodic memory content JSON and determine type."""
    try:
        data = json.loads(content_text)
        # Determine type based on JSON structure
        if 'use_cases' in data and 'title' in data:
            data['_type'] = 'REFLECTION'
        elif 'situation' in data and 'intent' in data:
            data['_type'] = 'LEARNED_PATTERN'
        else:
            data['_type'] = 'UNKNOWN'
        return data
    except json.JSONDecodeError:
        return {'_type': 'TEXT', 'text': content_text}


def filter_and_score_episodic(
    memories: List[dict],
    min_score: float
) -> List[dict]:
    """Filter episodic memories by relevance score and parse content."""
    filtered = []
    for m in memories:
        # API returns 'score', not 'relevanceScore'
        score = m.get('score', m.get('relevanceScore', 0))
        logger.info(f"Episodic memory score: {score}, keys: {list(m.keys())}")
        if score < min_score:
            logger.info(f"Filtering out memory with score {score} < {min_score}")
            continue

        content = m.get('content', {})
        text = content.get('text', '') if isinstance(content, dict) else str(content)
        logger.info(f"Memory content text (first 200 chars): {text[:200]}")
        parsed = parse_episodic_content(text)

        filtered.append({
            'score': score,
            'parsed': parsed,
            'namespaces': m.get('namespaces', []),
            'strategy_id': m.get('memoryStrategyId', '')
        })

    logger.info(f"Filtered episodic memories: {len(filtered)} of {len(memories)}")
    return sorted(filtered, key=lambda x: x['score'], reverse=True)


def format_episodic_context(memories: List[dict], max_chars: int) -> str:
    """Format episodic memories for injection into system prompt."""
    if not memories:
        return ""

    lines = ["\n## EPISODIC MEMORIES (Learned Patterns & Insights):"]
    char_count = len(lines[0])

    for m in memories:
        parsed = m.get('parsed', {})
        mem_type = parsed.get('_type', 'UNKNOWN')

        if mem_type == 'REFLECTION':
            title = parsed.get('title', 'Untitled')
            use_cases = parsed.get('use_cases', '')[:150]
            hints = parsed.get('hints', '')
            line = f"- [Insight] {title}: {use_cases}"
            if hints:
                line += f" (Hint: {hints[:50]})"
        elif mem_type == 'LEARNED_PATTERN':
            situation = parsed.get('situation', '')[:100]
            intent = parsed.get('intent', '')[:100]
            reflection = parsed.get('reflection', '')[:100]
            line = f"- [Pattern] Situation: {situation}... Intent: {intent}... Lesson: {reflection}"
        else:
            line = f"- [Memory] {str(parsed)[:150]}"

        if char_count + len(line) > max_chars:
            break

        lines.append(line)
        char_count += len(line)

    return "\n".join(lines) + "\n"


async def generate_memory_queries(prompt: str, model_name: str) -> List[str]:
    """
    Generate a few short free-form search queries to improve memory recall.

    This is part of the agent flow (a lightweight internal model pass), not a tool call.
    If parsing fails for any reason, falls back to [prompt].
    """
    system = """You generate search queries to retrieve relevant user memories.
Return ONLY valid JSON: {"queries": [..]}.
Rules:
- Max 3 queries.
- Short, natural-language.
- Cover: (1) task intent, (2) user preferences/background, (3) key entities/keywords.
- Do not include explanations."""

    user_message = f"User message:\n{prompt}\n\nJSON:"

    try:
        options = ClaudeAgentOptions(model=model_name)
        async with ClaudeSDKClient(options=options) as client:
            resp = await client.messages.create(
                messages=[UserMessage(content=[TextBlock(text=user_message)])],
                system=system,
                max_tokens=200,
            )

        text = ""
        for block in resp.content:
            if isinstance(block, TextBlock):
                text += block.text

        data = json.loads(text.strip())
        queries = [q.strip() for q in data.get("queries", []) if isinstance(q, str) and q.strip()]

        logger.info(f"Generated {len(queries)} memory queries: {queries[:3]}")

        # Always include the original prompt as the first query
        return [prompt] + queries[:3]

    except Exception as e:
        logger.warning("Failed to generate memory queries: %s", e)
        return [prompt]


def get_episodic_context(
    manager: MemorySessionManager,
    actor_id: str,
    session_id: str,
    queries: List[str],
    config: dict = None
) -> str:
    """Retrieve episodic memories from session and actor level namespaces.

    Args:
        manager: MemorySessionManager instance
        actor_id: Actor identifier
        session_id: Session identifier
        queries: List of search queries (from generate_memory_queries)
        config: Optional config override
    """
    if config is None:
        config = EPISODIC_MEMORY_CONFIG

    if not queries:
        return ""

    try:
        all_memories = []
        seen_ids = set()  # Deduplicate across queries

        # Find the episodic strategy ID
        episodic_strategy_id = get_episodic_strategy_id(manager)
        if not episodic_strategy_id:
            logger.info("No episodic strategy found, skipping episodic retrieval")
            return ""

        logger.info(f"Using episodic strategy: {episodic_strategy_id}")

        # Search with each query (limit to first 2 queries to control latency)
        for query in queries[:2]:
            # Search actor-level namespace (reflections - cross-session patterns)
            actor_namespace = f"/strategies/{episodic_strategy_id}/actors/{actor_id}"
            try:
                actor_mems = manager.search_long_term_memories(
                    query=query,
                    namespace_prefix=actor_namespace,
                    top_k=config["max_results_per_namespace"]
                )
                for m in actor_mems:
                    mem_id = m.get('memoryRecordId', '')
                    if mem_id and mem_id not in seen_ids:
                        seen_ids.add(mem_id)
                        all_memories.append(m)
            except Exception as e:
                logger.warning(f"Actor-level search failed for query '{query[:30]}': {e}")

            # Search session-level namespace (episodes - specific interactions)
            if session_id:
                session_namespace = f"/strategies/{episodic_strategy_id}/actors/{actor_id}/sessions/{session_id}"
                try:
                    session_mems = manager.search_long_term_memories(
                        query=query,
                        namespace_prefix=session_namespace,
                        top_k=config["max_results_per_namespace"]
                    )
                    for m in session_mems:
                        mem_id = m.get('memoryRecordId', '')
                        if mem_id and mem_id not in seen_ids:
                            seen_ids.add(mem_id)
                            all_memories.append(m)
                except Exception as e:
                    logger.warning(f"Session-level search failed for query '{query[:30]}': {e}")

            # Early exit if we have enough memories
            if len(all_memories) >= config["total_max_results"]:
                break

        logger.info(f"Episodic search found {len(all_memories)} unique memories")

        if not all_memories:
            return ""

        # Filter and format
        filtered = filter_and_score_episodic(all_memories, config["min_relevance_score"])
        truncated = filtered[:config["total_max_results"]]

        return format_episodic_context(truncated, config["max_context_chars"])

    except Exception as e:
        logger.warning("Failed to get episodic context: %s", e)
        return ""


async def store_turn(manager: MemorySessionManager, actor_id: str, session_id: str, user_msg: str, assistant_msg: str):
    """Store conversation turn in STM."""
    try:
        manager.add_turns(
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                ConversationalMessage(user_msg, MessageRole.USER),
                ConversationalMessage(assistant_msg, MessageRole.ASSISTANT)
            ]
        )
        logger.info("Stored conversation turn for actor_id=%s, session_id=%s", actor_id, session_id)
    except Exception as e:
        logger.warning("Failed to store turn: %s", e)


def get_subagents(model_name: str) -> dict:
    """Define sub-agents for parallel task execution.

    Demonstrates the Claude Agent SDK sub-agent capability with two specialized agents
    that can run tasks in parallel.
    """
    return {
        "web-researcher": AgentDefinition(
            description="Searches the web for information. Use for real-time data like prices, news, weather.",
            prompt="""You are a web research specialist. Your job is to find accurate, up-to-date information from the web.

When searching:
- Use browser tools to search and scrape web pages
- Extract the specific data requested
- Report findings concisely with the source""",
            tools=["mcp__browser__search_web", "mcp__browser__scrape_page"],
            model="haiku",  # Explicitly set model
        ),
        "code-executor": AgentDefinition(
            description="Executes Python code for calculations and data processing. Use for math, analysis, file operations.",
            prompt="""You are a Python code execution specialist. Your job is to write and run Python code to solve computational tasks.

When executing code:
- Write clean, efficient Python
- Use the code interpreter to run calculations
- Return results clearly formatted""",
            tools=["mcp__codeint__execute_code"],
            model="haiku",  # Explicitly set model
        ),
    }


@app.entrypoint
async def main(payload):
    """
    Entrypoint to the agent. Takes the user prompt, uses code interpreter tools to execute the prompt.
    Yields intermediate responses for streaming.
    """
    prompt = payload["prompt"]
    session_id = payload.get("session_id", "")
    actor_id = payload.get("actor_id", session_id or "default")
    agent_responses = []
    code_int_session_id = session_id

    # Determine model format based on CLAUDE_CODE_USE_BEDROCK environment variable
    use_bedrock = os.environ.get("CLAUDE_CODE_USE_BEDROCK", "1") == "1"
    model_name = (
        "global.anthropic.claude-haiku-4-5-20251001-v1:0"
        if use_bedrock
        else "claude-haiku-4-5-20251001"
    )
    logger.info(f"Using {'Bedrock' if use_bedrock else 'Anthropic API'} with model: {model_name}")

    # Initialize memory context
    stm_context = ""
    ltm_context = ""
    episodic_context = ""
    memory_manager = None

    try:
        memory_manager = get_memory_session_manager()
        stm_context = get_stm_context(memory_manager, actor_id, session_id)
        ltm_context = get_ltm_context(memory_manager, actor_id, prompt)

        # Episodic memory retrieval with LLM-generated queries
        memory_queries = await generate_memory_queries(prompt, model_name)
        episodic_context = get_episodic_context(
            memory_manager, actor_id, session_id, memory_queries
        )

        logger.info(
            f"Memory loaded - STM: {len(stm_context)} chars, "
            f"LTM: {len(ltm_context)} chars, "
            f"Episodic: {len(episodic_context)} chars"
        )
    except Exception as e:
        logger.warning(f"Memory unavailable, continuing without memory: {e}")

    # Log current working directory and Skills path for debugging
    current_dir = os.getcwd()
    skills_path = os.path.join(current_dir, ".claude", "skills")
    logger.info(f"Current working directory: {current_dir}")
    logger.info(f"Looking for Skills at: {skills_path}")
    if os.path.exists(skills_path):
        logger.info(f"Skills directory exists with: {os.listdir(skills_path)}")
    else:
        logger.warning(f"Skills directory not found at: {skills_path}")

    # Get Gateway authentication token
    gateway_token = None
    try:
        gateway_token = get_gateway_auth_token()
        logger.info("Gateway authentication successful")
    except Exception as e:
        logger.warning(f"Gateway authentication failed, continuing without gateway: {e}")

    # Build MCP servers config
    mcp_servers_config = {
        "codeint": code_int_mcp_server,
        "browser": browser_mcp_server,
    }

    # Add Gateway if authentication succeeded
    if gateway_token:
        mcp_servers_config["gateway"] = {
            "type": "http",
            "url": GATEWAY_CONFIG["url"],
            "headers": {"Authorization": f"Bearer {gateway_token}"}
        }

    # Get sub-agent definitions for parallel task execution
    subagents = get_subagents(model_name)

    options = ClaudeAgentOptions(
        mcp_servers=mcp_servers_config,
        model=model_name,
        cwd=os.getcwd(),  # Explicitly set working directory for Skills discovery
        setting_sources=["user", "project"],  # Enable loading Skills from filesystem
        permission_mode="bypassPermissions",  # Allow all tools including dynamically discovered ones
        # NOTE: allowed_tools is omitted to enable dynamic gateway tool discovery.
        # If sub-agents are not being invoked, you may need to add:
        #   allowed_tools=["Task", ...other tools...]
        # The Task tool is required for sub-agent invocation per SDK docs.
        agents=subagents,  # Enable parallel sub-agents (web-researcher, code-executor)
        system_prompt=f"""You are an AI assistant that helps users with tasks associated with code generation, execution, and web automation.
{stm_context}{ltm_context}{episodic_context}
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

  S3 STORAGE TOOLS:
  - mcp__codeint__upload_to_s3: Upload file from Code Interpreter to S3 bucket
    * Parameters: file_path (local path), s3_key (destination key), code_int_session_id
  - mcp__codeint__download_from_s3: Download file from S3 to Code Interpreter
    * Parameters: s3_key (source key), local_path (destination), code_int_session_id
  - mcp__codeint__list_s3_files: List files in S3 bucket
    * Parameters: prefix (filter by prefix), code_int_session_id

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

  ENTERPRISE GATEWAY (Dynamic Tool Discovery):
  You are connected to an Enterprise Gateway that provides access to a large library of business tools.
  You do not have all tools visible immediately. If a user asks for a task (e.g., 'check Jira tickets',
  'get weather', 'list ServiceNow incidents') and you do not see a specific tool for it:

  1. YOU MUST USE mcp__gateway__x_amz_bedrock_agentcore_search with a natural language query
     describing what capability you need (e.g., "Jira ticket management", "weather information").
  2. The search will return available tools that match your query.
  3. Once you discover the correct tool, you can then use it to fulfill the user's request.

  IMPORTANT: Always search the Gateway before saying you cannot do something. The Gateway may have
  the exact tool you need.

  SUB-AGENTS FOR PARALLEL EXECUTION:
  You have access to specialized sub-agents that can run tasks in parallel:

  - web-researcher: Searches the web for real-time information
    * Use for: current prices, news, weather, live data
    * Tools: browser search and scrape
    * Example: "What is the current Bitcoin price?"

  - code-executor: Runs Python code for calculations
    * Use for: math, statistics, data processing, file operations
    * Tools: code interpreter
    * Example: "Calculate compound interest on $10,000"

  WHEN TO USE PARALLEL SUB-AGENTS:
  When a user request contains TWO OR MORE independent tasks connected by "AND",
  "also", or similar, invoke the appropriate sub-agents in parallel:

  Example request: "Get the current Bitcoin price AND calculate compound interest
  on $10,000 at 5% for 10 years"

  → Invoke web-researcher for Bitcoin price
  → Invoke code-executor for compound interest calculation
  → Both run simultaneously, then combine results

  This is faster than doing tasks sequentially and demonstrates parallel execution.

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

    # Store conversation turn in memory
    if memory_manager and agent_responses:
        await store_turn(
            memory_manager, actor_id, session_id,
            prompt, "\n".join(agent_responses)
        )

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
