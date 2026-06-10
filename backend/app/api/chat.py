"""
Chat API — streaming and non-streaming endpoints.
employee_id is ALWAYS extracted from the validated JWT — never from request body.
"""
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.agent import HRAssistantAgent
from app.core.logging import audit_log, get_logger
from app.core.security import CurrentUser, get_current_user
from app.db import chat_repository

logger = get_logger(__name__)
router = APIRouter()

# Singleton agent (graph compiled once at startup)
_agent: HRAssistantAgent | None = None


def get_agent() -> HRAssistantAgent:
    global _agent
    if _agent is None:
        _agent = HRAssistantAgent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # None = create new session


class ChatResponse(BaseModel):
    session_id: str
    message: str
    tools_used: list[str]
    was_blocked: bool


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """
    Streaming chat endpoint — returns Server-Sent Events.
    
    The employee_id used in ALL tool calls comes from `current_user.employee_id`
    (extracted from JWT), never from the request body.
    """
    session_id = request.session_id or str(uuid.uuid4())

    # Load session history from DB
    history = await chat_repository.get_session_history(
        session_id=session_id,
        employee_id=current_user.employee_id,
        limit=10,  # Last 10 turns for context
    )

    # Audit: log this chat request
    await audit_log(
        employee_id=current_user.employee_id,
        action="chat_request",
        details={"session_id": session_id, "message_preview": request.message[:100]},
    )

    agent = get_agent()

    async def event_stream():
        full_response = []
        try:
            async for token in agent.chat_stream(
                message=request.message,
                employee_id=current_user.employee_id,  # From JWT — not request body
                session_id=session_id,
                history=history,
            ):
                full_response.append(token)
                # SSE format
                yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"

            # Save to DB
            final_response = "".join(full_response)
            await chat_repository.save_message(
                session_id=session_id,
                employee_id=current_user.employee_id,
                user_message=request.message,
                assistant_message=final_response,
            )

            # Send done event
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

        except Exception as e:
            logger.error("Chat stream error", error=str(e), employee_id=current_user.employee_id)
            yield f"data: {json.dumps({'error': 'حدث خطأ. يرجى المحاولة مرة أخرى.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering for SSE
        },
    )


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Non-streaming chat (for testing and clients that don't support SSE)."""
    session_id = request.session_id or str(uuid.uuid4())
    history = await chat_repository.get_session_history(
        session_id=session_id,
        employee_id=current_user.employee_id,
    )

    agent = get_agent()
    result = await agent.chat(
        message=request.message,
        employee_id=current_user.employee_id,
        session_id=session_id,
        history=history,
    )

    await chat_repository.save_message(
        session_id=session_id,
        employee_id=current_user.employee_id,
        user_message=request.message,
        assistant_message=result["text"],
    )

    return ChatResponse(
        session_id=session_id,
        message=result["text"],
        tools_used=result.get("tools_used", []),
        was_blocked=result.get("was_blocked", False),
    )


@router.get("/sessions")
async def list_sessions(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """List chat sessions for the current employee."""
    sessions = await chat_repository.list_sessions(employee_id=current_user.employee_id)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}/history")
async def get_session_history(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Get full message history for a session. Enforces ownership."""
    history = await chat_repository.get_session_history(
        session_id=session_id,
        employee_id=current_user.employee_id,  # Enforces ownership in SQL query
    )
    return {"session_id": session_id, "messages": history}
