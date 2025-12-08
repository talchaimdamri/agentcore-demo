import json
import uuid
import boto3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from botocore.exceptions import ClientError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = boto3.client("bedrock-agentcore")


class InvokeRequest(BaseModel):
    agent_arn: str
    prompt: str
    session_id: str = ""


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    async def stream():
        # Use existing session_id if provided, otherwise generate new one
        runtime_session_id = req.session_id if req.session_id else str(uuid.uuid4())
        payload = json.dumps({"prompt": req.prompt, "session_id": req.session_id})

        try:
            response = client.invoke_agent_runtime(
                agentRuntimeArn=req.agent_arn,
                runtimeSessionId=runtime_session_id,
                payload=payload.encode(),
                qualifier="DEFAULT",
            )

            # Get session_id from response metadata
            session_id = response.get("runtimeSessionId", "")
            streaming_body = response.get("response")

            for chunk in streaming_body.iter_lines():
                if not chunk:
                    continue
                chunk_str = chunk.decode("utf-8")
                if not chunk_str or chunk_str.startswith(":"):
                    continue
                if chunk_str.startswith("data:"):
                    chunk_str = chunk_str.split(":", 1)[1].strip()
                if chunk_str:
                    # Inject session_id into final event
                    try:
                        data = json.loads(chunk_str)
                        if data.get("type") == "final":
                            data["session_id"] = session_id
                            chunk_str = json.dumps(data)
                    except:
                        pass
                    yield f"data: {chunk_str}\n\n"

        except ClientError as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
