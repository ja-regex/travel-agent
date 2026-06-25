from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .agent import event_line, run_travel_agent
from .models import ChatMessage, ChatRequest


MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 4_000
MAX_CONVERSATION_CHARS = 16_000

app = FastAPI(title="Travel Companion Agent API", version="0.2.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "python"}


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    messages = [
        message
        for message in request.messages[-MAX_MESSAGES:]
        if message.content.strip()
    ]
    if not messages:
        raise HTTPException(status_code=400, detail="No messages supplied.")
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="Missing OPENAI_API_KEY.")
    if not os.getenv("TAVILY_API_KEY"):
        raise HTTPException(status_code=500, detail="Missing TAVILY_API_KEY.")

    conversation_chars = sum(len(message.content) for message in messages)
    if conversation_chars > MAX_CONVERSATION_CHARS or any(
        len(message.content) > MAX_MESSAGE_CHARS for message in messages
    ):
        raise HTTPException(
            status_code=413,
            detail=(
                "Trip request is too long. Keep each message under 4,000 "
                "characters and the conversation under 16,000."
            ),
        )

    async def safe_stream():
        try:
            async for line in run_travel_agent(
                [ChatMessage(role=item.role, content=item.content) for item in messages]
            ):
                yield line
        except Exception as error:
            yield event_line("error", message=str(error) or "Unexpected error.")

    return StreamingResponse(
        safe_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache, no-transform"},
    )
