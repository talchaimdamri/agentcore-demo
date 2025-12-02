import boto3
import json
import logging
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Code Interpreter session ID from sky_and_ai presentation
CODE_INT_SESSION_ID = "01KAYBSEZ9EN3TJNE8A4R9RGT7"

# Initialize the client
ci_client = boto3.client("bedrock-agentcore", "eu-central-1")

# File to download - try different paths
files_to_read = ["/workspace/sky_and_ai.pptx"]

def read_files_from_session(session_id: str, file_paths: list):
    """Read files from Code Interpreter session."""
    try:
        response = ci_client.invoke_code_interpreter(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            sessionId=session_id,
            name="readFiles",
            arguments={"paths": file_paths}
        )

        result = None
        for event in response["stream"]:
            if "result" in event:
                result = event["result"]  # Don't serialize - keep raw data

        return result
    except Exception as e:
        logger.error(f"Error reading files: {str(e)}")
        raise

def save_files_locally(files_data):
    """Save the files locally (handles both text and binary files)."""
    if "content" in files_data:
        for item in files_data["content"]:
            if item.get("type") == "resource" and "resource" in item:
                resource = item["resource"]
                file_uri = resource.get("uri", "")

                # Extract filename from URI
                local_filename = file_uri.split("/")[-1]

                # Check for binary data (base64 encoded)
                if "blob" in resource:
                    # Binary file (like .pptx)
                    blob_data = resource["blob"]
                    file_bytes = base64.b64decode(blob_data)
                    with open(local_filename, "wb") as f:
                        f.write(file_bytes)
                    logger.info(f"✓ Saved binary file: {local_filename} ({len(file_bytes)} bytes)")
                elif "text" in resource:
                    # Text file
                    file_content = resource["text"]
                    with open(local_filename, "w") as f:
                        f.write(file_content)
                    logger.info(f"✓ Saved text file: {local_filename}")
                else:
                    logger.warning(f"✗ No content found for: {file_uri}")
                    logger.warning(f"Resource keys: {resource.keys()}")

def main():
    logger.info("Reading presentation from Code Interpreter session...")
    logger.info(f"Session ID: {CODE_INT_SESSION_ID}")
    logger.info(f"Files to read: {files_to_read}\n")

    files_data = read_files_from_session(CODE_INT_SESSION_ID, files_to_read)

    logger.info("\nSaving files locally...")
    save_files_locally(files_data)

    logger.info("\n✅ Presentation downloaded successfully!")
    logger.info("You can now open 'sky_and_ai.pptx' with PowerPoint or Google Slides!")

if __name__ == "__main__":
    main()
