"""
Test browser automation through the agent.
This demonstrates how Claude uses browser automation tools.
"""

import json
import uuid
import boto3
import logging
from botocore.exceptions import ClientError, ReadTimeoutError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent_arn = "<agent-arn>"  # Replace with your agent ARN

# Initialize the Amazon Bedrock AgentCore client
agent_core_client = boto3.client("bedrock-agentcore")


def invoke_agent(prompt: str, session_id: str = ""):
    """Invoke the agent with a prompt."""
    runtime_session_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt, "session_id": session_id}).encode()

    logger.info("*" * 80)
    logger.info("Sending request: %s", prompt)
    logger.info("*" * 80)

    try:
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=runtime_session_id,
            payload=payload,
            qualifier="DEFAULT",
        )
        streaming_body = response.get("response")
        final_response = ""
        final_session_id = ""

        logger.info("*" * 80)
        logger.info("Streaming response...")
        logger.info("*" * 80)

        try:
            for chunk in streaming_body.iter_lines():
                if chunk:
                    chunk_str = chunk.decode("utf-8")

                    if not chunk_str or chunk_str.startswith(":"):
                        continue

                    # Handle SSE format
                    if chunk_str.startswith("data:"):
                        chunk_str = chunk_str.split(":", 1)[1].strip()

                    if chunk_str:
                        chunk_data = json.loads(chunk_str)

                        if chunk_data.get("type") == "text":
                            logger.info("\n📝 TEXT: %s", chunk_data.get("text"))

                        elif chunk_data.get("type") == "tool_use":
                            tool_name = chunk_data.get("tool_name")
                            tool_input = chunk_data.get("tool_input")
                            logger.info("\n🔧 TOOL USED: %s", tool_name)
                            logger.info("   Input: %s", json.dumps(tool_input, indent=2))

                        elif chunk_data.get("type") == "final":
                            final_response = chunk_data.get("response", "")
                            final_session_id = chunk_data.get("session_id", "")

        except ReadTimeoutError as e:
            logger.error("Request failed: %s", str(e))

        logger.info("*" * 80)
        logger.info("Streaming complete")
        logger.info("*" * 80)

        return {
            "response": final_response if final_response else "No response received",
            "session_id": final_session_id,
        }

    except ClientError as e:
        logger.warning("Request failed: %s", str(e))
        raise


def main():
    """Test various browser automation scenarios."""

    # Test 1: Simple web search
    logger.info("\n" + "=" * 80)
    logger.info("TEST 1: Search Amazon for laptops")
    logger.info("=" * 80)

    prompt = """
    Search Amazon for "laptop" and tell me what you find.
    Use the browser automation tool to:
    1. Navigate to amazon.com
    2. Search for "laptop"
    3. Take a screenshot
    4. Tell me about the results
    """

    result = invoke_agent(prompt)
    logger.info("\n✅ Final Response:\n%s", result["response"])

    # Test 2: Web scraping
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Scrape example.com")
    logger.info("=" * 80)

    prompt = """
    Go to example.com and scrape the page content.
    Extract the h1 heading and all paragraph text.
    """

    result = invoke_agent(prompt)
    logger.info("\n✅ Final Response:\n%s", result["response"])

    # Test 3: Screenshot
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Take screenshot of a website")
    logger.info("=" * 80)

    prompt = """
    Take a full-page screenshot of https://www.anthropic.com
    """

    result = invoke_agent(prompt)
    logger.info("\n✅ Final Response:\n%s", result["response"])


if __name__ == "__main__":
    logger.info("Starting Browser Automation Agent Tests")
    logger.info("Make sure BROWSER_TOOL_ID and TOOL_RESOURCE_ARN are set as environment variables\n")

    main()

    logger.info("\n" + "=" * 80)
    logger.info("All tests completed!")
    logger.info("=" * 80)
