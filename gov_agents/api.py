import os
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from langchain_core.messages import HumanMessage

from agent import AgentManager

# Request model
class ChatRequest(BaseModel):
    message: str

# Global agent manager
agent_manager = AgentManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Initializing agent...")
    try:
        await agent_manager.initialize()
        print("Agent initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
    
    yield
    
    # Shutdown
    print("Shutting down agent...")
    await agent_manager.aclose()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(lifespan=lifespan, title="Gov Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def stream_generator(query: str) -> AsyncGenerator[str, None]:
    """Generates a stream of events from the agent."""
    if not agent_manager.agent_executor:
        yield "data: Error: Agent not initialized.\n\n"
        yield "data: [DONE]\n\n"
        return

    try:
        # Stream events from the agent
        # We use astream_events to get detailed updates (tool calls, etc.)
        async for event in agent_manager.agent_executor.astream_events(
            {"input": query},
            version="v2"
        ):
            kind = event["event"]
            
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    # Send text chunk
                    yield f"data: {content}\n\n"
            
            elif kind == "on_tool_start":
                tool_name = event["name"]
                inputs = event["data"].get("input", {})
                yield f"data: [TOOL_START] {tool_name}: {inputs}\n\n"
                
            elif kind == "on_tool_end":
                tool_name = event["name"]
                yield f"data: [TOOL_END] {tool_name}\n\n"
            
            elif kind == "on_chain_end":
                # Check if this is the final output
                output = event["data"].get("output", {})
                if isinstance(output, dict) and "output" in output:
                    # This is the final response
                    pass

    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"data: Error: {str(e)}\n\n"
    
    yield "data: [DONE]\n\n"

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that streams the agent's response.
    """
    return StreamingResponse(
        stream_generator(request.message),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "agent_initialized": agent_manager.agent_executor is not None}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
