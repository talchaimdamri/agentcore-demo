# Simple AgentCore Invoke UI

## Overview
Minimal UI to invoke AgentCore agents (~140 lines total):
- User manually pastes agent ARN (single text input)
- Simple chat interface
- Streaming response display
- Session continuation using AWS-generated session_id

## Key Rules
1. **Agent ARN**: User manually pastes the full ARN (no agent list/dropdown)
2. **Session ID**:
   - NEVER generate session_id yourself - it's an internal AWS UUID
   - First request: send empty session_id
   - AWS returns session_id in response header (e.g., `Session: e76d886d-cd0b-4bde-8a48-61f5cb04a309`)
   - Subsequent requests: use the returned session_id to continue conversation

---

## Tasks

### 1. Create api.py (~50 lines)
- `/invoke` POST endpoint (SSE streaming)
- Accepts: `{agent_arn, prompt, session_id (optional)}`
- Calls `agentcore invoke` CLI
- Streams JSON response lines
- CORS enabled

### 2. Create invoke.html (~90 lines)
- Agent ARN text input (user pastes manually)
- Message input + Send button
- Chat display (user/agent messages)
- Extract session_id from response, store for next message

### 3. Test for user
- Paste ARN, send message, see streaming response
- Send another message - verify session continues

---

## File Structure
```
agentcore-ui/
├── invoke.html           # Single-page UI
├── api.py                # Backend
└── PLAN_SIMPLE_INVOKE.md # This plan
```

---

## Response Format (from agentcore CLI) - mistake! 
```
{"type": "text", "text": "Hello!", "session_id": ""}
{"type": "final", "response": "Hello!", "session_id": "e76d886d-cd0b-4bde-8a48-61f5cb04a309"}
```
The session_id appears in the "final" event - extract and store it.

---

## Commands
```bash
# Backend
cd agentcore-ui
python3 -m uvicorn api:app --reload --port 8080

# Frontend
open invoke.html
```
