import json
import os
import signal
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

import yaml
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pathlib import Path

from kuafu_llm_infra import create_client
from llm_infra_test.tools import TOOL_DEFINITIONS, TOOL_EXECUTORS

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Config loading (env var substitution)
# ============================================================================

def load_yaml_config(path: str) -> dict:
    with open(path) as f:
        raw = f.read()
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    return yaml.safe_load(raw)


# ============================================================================
# App lifecycle
# ============================================================================

llm_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client
    config = load_yaml_config(str(PROJECT_ROOT / "config.yaml"))
    llm_client = create_client(config)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(llm_client.shutdown()))

    yield
    await llm_client.shutdown()


app = FastAPI(title="llm-infra-test", lifespan=lifespan)


# ============================================================================
# Request / Response models
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    stream: bool = False
    use_tools: bool = False
    business_key: str = "chat"
    module: str = "test"
    app_id: str = "123"


# ============================================================================
# Endpoints
# ============================================================================

@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": "user", "content": req.message}]
    labels = {"app_id": req.app_id}
    tools = TOOL_DEFINITIONS if req.use_tools else None
    strategy = req.business_key if not req.stream else "chat"

    if req.stream:
        return StreamingResponse(
            _stream_chat(messages, req.model, labels, tools),
            media_type="text/event-stream",
        )

    # Non-streaming
    response = await llm_client.chat.completions.create(
        model=req.model,
        messages=messages,
        business_key=strategy if not req.stream else "chat_block",
        labels=labels,
        tools=tools,
        tool_choice="auto" if tools else None,
    )

    # If the model called a tool, execute it and do a second round
    if response.tool_calls:
        tool_results = _execute_tools(response.tool_calls)
        messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
        for tr in tool_results:
            messages.append(tr)

        response = await llm_client.chat.completions.create(
            model=req.model,
            messages=messages,
            business_key="chat_block",
            labels=labels,
        )

    return {
        "content": response.content,
        "model": response.model,
        "usage": response.usage,
    }


async def _stream_chat(messages, model, labels, tools):
    stream = await llm_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        business_key="chat",
        labels=labels,
        tools=tools,
        tool_choice="auto" if tools else None,
    )
    async for chunk in stream:
        if chunk.content:
            yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _execute_tools(tool_calls) -> list:
    results = []
    for tc in tool_calls:
        name = tc.function.name if hasattr(tc, "function") else tc.get("function", {}).get("name")
        args_raw = tc.function.arguments if hasattr(tc, "function") else tc.get("function", {}).get("arguments", "{}")
        tool_id = tc.id if hasattr(tc, "id") else tc.get("id", name)

        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        executor = TOOL_EXECUTORS.get(name)
        if executor:
            result = executor(args)
        else:
            result = {"error": f"Unknown tool: {name}"}

        results.append({
            "role": "tool",
            "tool_call_id": tool_id,
            "content": json.dumps(result, ensure_ascii=False),
        })
    return results


@app.get("/tools")
async def list_tools():
    """List available tools."""
    return {"tools": [t["function"]["name"] for t in TOOL_DEFINITIONS]}


@app.get("/health")
async def health():
    return {"status": "ok"}
