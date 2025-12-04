"""In process MCP server for Code Interpreter."""

from .client import CodeInterpreterClient
from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any
import json
import logging

logger = logging.getLogger(__name__)

# Initialize the client
client = CodeInterpreterClient()


@tool(
    "execute_code",
    "Execute code using Code Interpreter. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"code": str, "language": str, "code_int_session_id": str},
)
async def execute_code(args: dict[str, Any]) -> dict[str, Any]:
    result = client.execute_code(
        args.get("code"),
        args.get("language", "python"),
        args.get("code_int_session_id", ""),
    )
    response_text = result.model_dump_json(indent=2)

    return {"content": [{"type": "text", "text": response_text}]}


@tool(
    "execute_command",
    "Execute command using Code Interpreter. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"command": str, "code_int_session_id": str},
)
async def execute_command(args: dict[str, Any]) -> dict[str, Any]:
    result = client.execute_command(
        args.get("command"), args.get("code_int_session_id", "")
    )
    response_text = result.model_dump_json(indent=2)

    return {"content": [{"type": "text", "text": response_text}]}


@tool(
    "write_files",
    "Write files to the Code Interpreter environment. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"files_to_create": list, "code_int_session_id": str},
)
async def write_files(args: dict[str, Any]) -> dict[str, Any]:
    files_to_create = args["files_to_create"]
    if isinstance(files_to_create, str):
        files_to_create = json.loads(files_to_create)

    result = client.write_files(files_to_create, args.get("code_int_session_id", ""))
    response_text = result.model_dump_json(indent=2)

    return {"content": [{"type": "text", "text": response_text}]}


@tool(
    "read_files",
    "Read files from the Code Interpreter environment. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"paths": list, "code_int_session_id": str},
)
async def read_files(args: dict[str, Any]) -> dict[str, Any]:
    paths = args["paths"]
    if isinstance(paths, str):
        paths = json.loads(paths)
    result = client.read_files(paths, args.get("code_int_session_id", ""))
    response_text = result.model_dump_json(indent=2)

    return {"content": [{"type": "text", "text": response_text}]}


@tool(
    "upload_to_s3",
    "Upload a file from Code Interpreter to S3 bucket. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"file_path": str, "s3_key": str, "code_int_session_id": str},
)
async def upload_to_s3(args: dict[str, Any]) -> dict[str, Any]:
    file_path = args.get("file_path")
    s3_key = args.get("s3_key")
    code = f'''
import boto3
s3 = boto3.client('s3')
bucket = 'agentcore-artifacts-597088042181'
s3.upload_file('{file_path}', bucket, '{s3_key}')
print(f"Uploaded {file_path} to s3://{{bucket}}/{s3_key}")
'''
    result = client.execute_code(code, "python", args.get("code_int_session_id", ""))
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


@tool(
    "download_from_s3",
    "Download a file from S3 to Code Interpreter. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"s3_key": str, "local_path": str, "code_int_session_id": str},
)
async def download_from_s3(args: dict[str, Any]) -> dict[str, Any]:
    s3_key = args.get("s3_key")
    local_path = args.get("local_path")
    code = f'''
import boto3
s3 = boto3.client('s3')
bucket = 'agentcore-artifacts-597088042181'
s3.download_file(bucket, '{s3_key}', '{local_path}')
print(f"Downloaded s3://{{bucket}}/{s3_key} to {local_path}")
'''
    result = client.execute_code(code, "python", args.get("code_int_session_id", ""))
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


@tool(
    "list_s3_files",
    "List files in the S3 bucket. IMPORTANT: For the first call, pass an empty string for code_int_session_id to create a new session.",
    {"prefix": str, "code_int_session_id": str},
)
async def list_s3_files(args: dict[str, Any]) -> dict[str, Any]:
    prefix = args.get("prefix", "")
    code = f'''
import boto3
s3 = boto3.client('s3')
bucket = 'agentcore-artifacts-597088042181'
response = s3.list_objects_v2(Bucket=bucket, Prefix='{prefix}')
files = response.get('Contents', [])
if files:
    for obj in files:
        print(f"{{obj['Key']}} ({{obj['Size']}} bytes)")
else:
    print("No files found with prefix '{prefix}'")
'''
    result = client.execute_code(code, "python", args.get("code_int_session_id", ""))
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


code_int_mcp_server = create_sdk_mcp_server(
    name="codeinterpretertools",
    version="1.0.0",
    tools=[execute_code, execute_command, write_files, read_files, upload_to_s3, download_from_s3, list_s3_files],
)
