import json
import uuid
import boto3
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from botocore.exceptions import ClientError

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentcore-ui")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = boto3.client("bedrock-agentcore")


@app.get("/health")
async def health():
    return {"status": "ok"}


class InvokeRequest(BaseModel):
    agent_arn: str
    prompt: str
    session_id: str = ""
    user_name: str = ""


@app.post("/invoke")
async def invoke(req: InvokeRequest):
    async def stream():
        # Use existing session_id if provided, otherwise generate new one
        runtime_session_id = req.session_id if req.session_id else str(uuid.uuid4())
        payload = json.dumps({
                "prompt": req.prompt,
                "session_id": runtime_session_id,
                "actor_id": req.user_name,
                "user_name": req.user_name
            })

        # Log the request
        logger.info("=" * 80)
        logger.info(f"[{datetime.now().isoformat()}] INVOKE REQUEST")
        logger.info(f"  Agent ARN: {req.agent_arn}")
        logger.info(f"  Session ID: {runtime_session_id}")
        logger.info(f"  Actor ID: {req.user_name}")
        logger.info(f"  Prompt: {req.prompt[:100]}{'...' if len(req.prompt) > 100 else ''}")
        logger.info("-" * 40)
        logger.info("  RAW PAYLOAD:")
        logger.info(f"  {payload}")
        logger.info("-" * 40)

        try:
            response = client.invoke_agent_runtime(
                agentRuntimeArn=req.agent_arn,
                runtimeSessionId=runtime_session_id,
                payload=payload.encode(),
                qualifier="DEFAULT",
            )

            # Log response metadata
            session_id = response.get("runtimeSessionId", "")
            logger.info(f"  Response Session ID: {session_id}")
            logger.info(f"  Response Metadata: {response.get('ResponseMetadata', {})}")
            logger.info("-" * 40)
            logger.info("  STREAMING EVENTS:")

            streaming_body = response.get("response")
            event_count = 0

            for chunk in streaming_body.iter_lines():
                if not chunk:
                    continue
                chunk_str = chunk.decode("utf-8")
                if not chunk_str or chunk_str.startswith(":"):
                    continue
                if chunk_str.startswith("data:"):
                    chunk_str = chunk_str.split(":", 1)[1].strip()
                if chunk_str:
                    event_count += 1
                    # Log each event
                    try:
                        data = json.loads(chunk_str)
                        event_type = data.get("type", "unknown")
                        if event_type == "text":
                            text_preview = data.get("text", "")[:50]
                            logger.info(f"    [{event_count}] text: {text_preview}...")
                        elif event_type == "tool_use":
                            logger.info(f"    [{event_count}] tool_use: {data.get('tool_name', 'unknown')}")
                        elif event_type == "final":
                            data["session_id"] = session_id
                            chunk_str = json.dumps(data)
                            logger.info(f"    [{event_count}] final: session={session_id}")
                        elif event_type == "error":
                            logger.info(f"    [{event_count}] error: {data.get('error', 'unknown')}")
                        else:
                            logger.info(f"    [{event_count}] {event_type}: {chunk_str[:80]}")
                    except:
                        logger.info(f"    [{event_count}] raw: {chunk_str[:80]}")
                    yield f"data: {chunk_str}\n\n"

            logger.info(f"  Total events: {event_count}")
            logger.info("=" * 80)

        except ClientError as e:
            logger.error(f"  ERROR: {str(e)}")
            logger.info("=" * 80)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
