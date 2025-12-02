"""
Quick script to get the cats presentation as base64 using the agent.
Run this, then save the base64 output to a file and decode it.
"""
import json
import uuid
import boto3
import base64

agent_arn = "arn:aws:bedrock-agentcore:eu-central-1:851725646055:runtime/claude_ci_agent-a4jvmjgbfa"
agent_core_client = boto3.client("bedrock-agentcore", region_name="eu-central-1")

runtime_session_id = str(uuid.uuid4())

# Ask agent to read file and output base64
prompt = """Read the cats_presentation.pptx file from the Code Interpreter session,
encode it as base64, and print ONLY the base64 string (no other text).
Use this session ID: 01KATM1PFJET8VFVAAT2BPH3FB"""

payload = json.dumps({
    "prompt": prompt,
    "session_id": "01KATM1PFJET8VFVAAT2BPH3FB"
}).encode()

print("Invoking agent to get base64 encoded presentation...")

response = agent_core_client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,
    runtimeSessionId=runtime_session_id,
    payload=payload,
    qualifier="DEFAULT",
)

streaming_body = response.get("response")
full_response = ""

for chunk in streaming_body.iter_lines():
    if chunk:
        chunk_str = chunk.decode("utf-8")
        if chunk_str.startswith("data:"):
            data_str = chunk_str[5:].strip()
            try:
                data = json.loads(data_str)
                if data.get("type") == "text":
                    text_content = data.get("text", "")
                    full_response += text_content
                    print(text_content, end="", flush=True)
            except json.JSONDecodeError:
                pass

print("\n\nFull response received. Saving to file...")

# Try to extract base64 from response and decode
lines = full_response.strip().split('\n')
for line in lines:
    line = line.strip()
    # Look for a long base64 string
    if len(line) > 100 and not line.startswith('#') and not line.startswith('```'):
        try:
            # Try to decode
            decoded = base64.b64decode(line)
            if decoded[:2] == b'PK':  # ZIP file magic bytes (PPTX is a ZIP)
                with open('cats_presentation.pptx', 'wb') as f:
                    f.write(decoded)
                print(f"\n✅ Successfully decoded and saved cats_presentation.pptx ({len(decoded)} bytes)")
                break
        except:
            continue
