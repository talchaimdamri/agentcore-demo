import boto3
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Code Interpreter session ID from the previous execution
CODE_INT_SESSION_ID = "01KATM1PFJET8VFVAAT2BPH3FB"

# Initialize the client
ci_client = boto3.client("bedrock-agentcore", "eu-central-1")

# Files to download
files_to_read = [
    "cats_presentation_base64.txt"
]

def read_files_from_session(session_id: str, file_paths: list):
    """Read files from Code Interpreter session."""
    try:
        response = ci_client.invoke_code_interpreter(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            sessionId=session_id,
            name="readFiles",
            arguments={"paths": file_paths}
        )

        output = ""
        for event in response["stream"]:
            if "result" in event:
                output = json.dumps(event["result"], indent=2)

        result = json.loads(output)
        return result
    except Exception as e:
        logger.error(f"Error reading files: {str(e)}")
        raise

def save_files_locally(files_data):
    """Save the files locally."""
    if "content" in files_data:
        for item in files_data["content"]:
            if item.get("type") == "resource" and "resource" in item:
                resource = item["resource"]
                file_uri = resource.get("uri", "")
                file_content = resource.get("text", "")

                if file_content:
                    # Extract filename from URI (e.g., "file:///retail_store_orders.csv")
                    local_filename = file_uri.split("/")[-1]
                    with open(local_filename, "w") as f:
                        f.write(file_content)
                    logger.info(f"✓ Saved: {local_filename}")
                else:
                    logger.warning(f"✗ No content for: {file_uri}")

def main():
    logger.info("Reading files from Code Interpreter session...")
    logger.info(f"Session ID: {CODE_INT_SESSION_ID}")
    logger.info(f"Files to read: {files_to_read}\n")

    files_data = read_files_from_session(CODE_INT_SESSION_ID, files_to_read)

    logger.info("\nSaving files locally...")
    save_files_locally(files_data)

    logger.info("\n✅ All files downloaded successfully!")

if __name__ == "__main__":
    main()
