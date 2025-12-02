import boto3
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CODE_INT_SESSION_ID = "01KATMYCCH9ZMPTV7KQHRWV3GK"
ci_client = boto3.client("bedrock-agentcore", "eu-central-1")

files_to_read = ["microsoft_board_presentation.pptx"]

def read_binary_files_from_session(session_id: str, file_paths: list):
    """Read binary files from Code Interpreter session without JSON serialization."""
    try:
        response = ci_client.invoke_code_interpreter(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            sessionId=session_id,
            name="readFiles",
            arguments={"paths": file_paths}
        )

        # Process stream without JSON serialization
        result = None
        for event in response["stream"]:
            if "result" in event:
                result = event["result"]  # Keep raw result without JSON serialization
                break

        return result
    except Exception as e:
        logger.error(f"Error reading files: {str(e)}")
        raise

def save_binary_files(files_data):
    """Save binary files from the response."""
    if not files_data or "content" not in files_data:
        logger.error("No content found in response")
        return

    for item in files_data["content"]:
        if item.get("type") == "resource" and "resource" in item:
            resource = item["resource"]
            file_uri = resource.get("uri", "")
            local_filename = file_uri.split("/")[-1]

            logger.info(f"Resource keys: {resource.keys()}")

            # Try different possible keys for binary data
            if "blob" in resource:
                # Base64 encoded binary
                blob_data = resource["blob"]
                if isinstance(blob_data, bytes):
                    file_bytes = blob_data
                else:
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
                logger.warning(f"Unknown resource format. Keys: {resource.keys()}")

def main():
    logger.info("Attempting direct binary download...")
    logger.info(f"Session ID: {CODE_INT_SESSION_ID}")
    logger.info(f"Files: {files_to_read}\n")

    files_data = read_binary_files_from_session(CODE_INT_SESSION_ID, files_to_read)

    if files_data:
        logger.info("Processing response...")
        save_binary_files(files_data)
        logger.info("\n✅ Download complete!")
    else:
        logger.error("No data received")

if __name__ == "__main__":
    main()
