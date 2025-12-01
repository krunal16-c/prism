import asyncio
import os
import sys
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack
from dotenv import load_dotenv

load_dotenv()


from pydantic import create_model, Field
from langchain_core.tools import Tool, StructuredTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.types import CallToolResult, TextContent

from tools.file_ops import download_file, unzip_file, read_csv_head, list_files

# Configuration
MCP_SERVERS = [
    "http://localhost:8001/sse",
    "http://localhost:8002/sse"
]

def json_schema_to_pydantic(schema: Dict[str, Any], name: str) -> Any:
    """Converts a JSON schema to a Pydantic model."""
    fields = {}
    if "properties" in schema:
        for field_name, field_info in schema["properties"].items():
            field_type = str
            if field_info.get("type") == "integer":
                field_type = int
            elif field_info.get("type") == "number":
                field_type = float
            elif field_info.get("type") == "boolean":
                field_type = bool
            elif field_info.get("type") == "array":
                field_type = List[Any] # Simplified
            
            # Determine if required
            required = field_name in schema.get("required", [])
            default = field_info.get("default", ... if required else None)
            
            fields[field_name] = (field_type, Field(default=default, description=field_info.get("description", "")))
    
    return create_model(f"{name}Arguments", **fields)

class MCPToolWrapper:
    """Wraps an MCP tool for use with LangChain."""
    
    def __init__(self, session: ClientSession, name: str, description: str, input_schema: Dict[str, Any]):
        self.session = session
        self.name = name
        self.description = description
        self.input_schema = input_schema

    async def _arun(self, **kwargs) -> str:
        """Execute the tool asynchronously."""
        print(f"DEBUG: Calling {self.name} with args: {kwargs}")
        try:
            result: CallToolResult = await self.session.call_tool(self.name, arguments=kwargs)
            
            output = []
            if result.content:
                for content in result.content:
                    if isinstance(content, TextContent):
                        output.append(content.text)
                    else:
                        output.append(f"[{content.type} content]")
            
            if result.isError:
                return f"Error: {' '.join(output)}"
            
            final_output = "\n".join(output)
            return final_output if final_output.strip() else "Tool executed successfully but returned no output."
        except Exception as e:
            return f"Error calling tool {self.name}: {str(e)}"

    def to_langchain_tool(self) -> StructuredTool:
        """Converts to a LangChain StructuredTool."""
        args_schema = json_schema_to_pydantic(self.input_schema, self.name)
        
        return StructuredTool.from_function(
            func=None, # Sync not supported
            coroutine=self._arun,
            name=self.name,
            description=self.description,
            args_schema=args_schema
        )

async def connect_to_mcp_server(url: str, stack: AsyncExitStack) -> ClientSession:
    """Connects to an MCP server via SSE."""
    print(f"Connecting to MCP server at {url}...")
    # The sse_client context manager yields (read_stream, write_stream)
    # We need to keep it open, so we use AsyncExitStack
    streams = await stack.enter_async_context(sse_client(url))
    session = await stack.enter_async_context(ClientSession(streams[0], streams[1]))
    await session.initialize()
    return session

async def get_agent_executor():
    """Initializes and returns the agent executor."""
    # Check for API Key
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    async with AsyncExitStack() as stack:
        # Note: We can't easily yield the stack from here without using a context manager for the whole app.
        # For the API, we might need a different approach to manage the connection lifecycle.
        # However, for now, let's assume we create a new connection per request or use a global one.
        # A better approach for FastAPI is to use lifespan events.
        pass
    
    # To make this reusable, we need to separate tool fetching from agent creation.
    # But MCP tools need an active connection.
    # Let's create a class that manages the connection and agent.
    pass

class AgentManager:
    def __init__(self):
        self.stack = AsyncExitStack()
        self.agent_executor = None

    async def initialize(self):
        tools = []
        # 1. Connect to MCP Servers and fetch tools
        for url in MCP_SERVERS:
            try:
                session = await connect_to_mcp_server(url, self.stack)
                mcp_tools = await session.list_tools()
                
                for tool_info in mcp_tools.tools:
                    wrapper = MCPToolWrapper(
                        session=session,
                        name=tool_info.name,
                        description=tool_info.description or "",
                        input_schema=tool_info.inputSchema
                    )
                    tools.append(wrapper.to_langchain_tool())
                    print(f"Added MCP tool: {tool_info.name}")
            except Exception as e:
                print(f"Failed to connect to {url}: {e}")

        # 2. Add Local Tools
        tools.append(StructuredTool.from_function(download_file))
        tools.append(StructuredTool.from_function(unzip_file))
        tools.append(StructuredTool.from_function(read_csv_head))
        tools.append(StructuredTool.from_function(list_files))

        # 3. Setup Agent with OpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=2000)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are PRISM AI, an intelligent agent for Canadian government infrastructure data. "
                       "Your goal is to provide deep insights about bridges, roads, and infrastructure conditions.\n\n"
                       "You can help with:\n"
                       "- Finding and analyzing infrastructure datasets\n"
                       "- Answering questions about bridge and road conditions\n"
                       "- Providing funding optimization recommendations\n"
                       "- Forecasting infrastructure degradation\n\n"
                       "Follow this workflow when asked to find data:\n"
                       "1. **Search**: Use available tools to find relevant datasets.\n"
                       "2. **Investigate**: Understand the data structure and resources.\n"
                       "3. **Download & Process**: Use `download_file` to get resources. If it's a zip, use `unzip_file`.\n"
                       "4. **Analyze**: Use `read_csv_head` to inspect the actual data content.\n"
                       "5. **Answer**: Provide a comprehensive answer based on the actual data you processed.\n\n"
                       "Always explain your reasoning clearly."),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_openai_tools_agent(llm, tools, prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return self.agent_executor

    async def aclose(self):
        await self.stack.aclose()

async def main():
    manager = AgentManager()
    try:
        agent_executor = await manager.initialize()
        print("\nAgent is ready! Type 'exit' to quit.")
        while True:
            try:
                user_input = input("\nUser: ")
                if user_input.lower() in ["exit", "quit"]:
                    break
                
                print("\nAgent is thinking...")
                result = await agent_executor.ainvoke({"input": user_input})
                print(f"\nAgent: {result['output']}")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    finally:
        await manager.aclose()

if __name__ == "__main__":
    asyncio.run(main())

