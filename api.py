"""Riven API Server - HTTP API for core management and messaging."""

import os
import json
import uuid
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from core_manager import get_manager, CoreManager
from core import get_core


# ============== MODELS ==============

class SessionCreate(BaseModel):
    core_name: Optional[str] = None


class MessageSend(BaseModel):
    message: str
    stream: bool = False


# ============== API ==============

app = FastAPI(title="Riven API", version="1.0.0")
manager: CoreManager = get_manager()


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "riven": "codehammer"}


@app.get("/api/v1/cores")
def list_cores():
    """List available cores."""
    return {"cores": manager.list()}


@app.post("/api/v1/sessions")
def create_session(req: SessionCreate):
    """Create a new session."""
    result = manager.start(core_name=req.core_name)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message"))
    return result


@app.get("/api/v1/sessions")
def list_sessions():
    """List running sessions."""
    return {"sessions": manager.list_sessions()}


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str):
    """Get session info."""
    if not manager.exists(session_id):
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "core_name": manager.get_current(),
    }


@app.delete("/api/v1/sessions/{session_id}")
def delete_session(session_id: str):
    """Stop a session."""
    result = manager.stop(session_id)
    return result


@app.post("/api/v1/sessions/{session_id}/messages")
async def send_message(session_id: str, req: MessageSend):
    """Send a message to a session.
    
    If stream=true, returns SSE with real-time tokens.
    Otherwise returns complete response.
    """
    # Get session info
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    core_name = session.get("core_name", "code_hammer")
    
    if req.stream:
        # Real streaming - use core.run_stream()
        import asyncio
        
        async def generate():
            try:
                core = get_core(core_name)
                async for event in core.run_stream(req.message):
                    if "error" in event:
                        yield f"data: {json.dumps({'error': event['error']})}\n\n"
                        break
                    if "token" in event:
                        yield f"data: {json.dumps({'token': event['token']})}\n\n"
                    if event.get("done"):
                        yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    # Non-streaming - wait for complete response
    result = manager.send(session_id, req.message)
    
    if not result.get("ok"):
        raise HTTPException(400, result.get("error"))
    
    if result.get("queued"):
        import time
        output = ""
        for _ in range(60):
            time.sleep(0.5)
            messages = manager.receive(session_id)
            if messages:
                output = messages[0]
                break
        else:
            output = "Timeout waiting for response"
    else:
        output = result.get("output", "")
    
    return {"output": output}


@app.get("/api/v1/sessions/{session_id}/messages")
def poll_messages(session_id: str):
    """Poll for messages from a session."""
    messages = manager.receive(session_id)
    return {"messages": messages}


# ============== RUN ==============

def run(host: str = "0.0.0.0", port: int = 8080):
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run(host="0.0.0.0", port=8080)