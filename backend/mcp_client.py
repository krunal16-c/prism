"""
MCP Client Service
Connects to Government of Canada MCP Servers for real infrastructure data
- Dataset MCP (port 9000): Dataset discovery and search  
- Transportation MCP (port 9001): Bridge conditions, infrastructure costs

Uses MCP SDK with SSE (Server-Sent Events) transport for real-time data.
"""

import httpx
import json
import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager

# MCP SDK imports
from mcp import ClientSession
from mcp.client.sse import sse_client

# MCP Server Configuration (SSE endpoints)
MCP_TRANSPORTATION_URL = os.getenv("MCP_TRANSPORTATION_URL", "http://localhost:8001/sse")
MCP_DATASET_URL = os.getenv("MCP_DATASET_URL", "http://localhost:9000/sse")

# Timeout settings
REQUEST_TIMEOUT = 30.0


def check_mcp_server_running(base_url: str) -> bool:
    """Check if an MCP server is running by checking if the port responds"""
    try:
        # Remove /sse suffix for port check
        check_url = base_url.replace("/sse", "")
        import socket
        from urllib.parse import urlparse
        parsed = urlparse(check_url)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((parsed.hostname or 'localhost', parsed.port or 80))
        sock.close()
        return result == 0
    except Exception:
        return False


class AsyncMCPClient:
    """
    Async client for MCP servers using SSE transport.
    Uses the official MCP SDK for proper protocol handling.
    """
    
    def __init__(self, sse_url: str):
        self.sse_url = sse_url
        self._session: Optional[ClientSession] = None
    
    @asynccontextmanager
    async def connect(self):
        """Connect to the MCP server via SSE"""
        async with sse_client(self.sse_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict]:
        """Call an MCP tool and return the result"""
        try:
            async with self.connect() as session:
                result = await session.call_tool(tool_name, arguments)
                # Parse the result content
                if result and result.content:
                    for content in result.content:
                        if hasattr(content, 'text'):
                            try:
                                return json.loads(content.text)
                            except json.JSONDecodeError:
                                return {"text": content.text}
                return None
        except Exception as e:
            print(f"MCP tool call failed for {tool_name}: {e}")
            return None
    
    async def list_tools(self) -> Optional[List[Dict]]:
        """List available tools from the MCP server"""
        try:
            async with self.connect() as session:
                result = await session.list_tools()
                if result and result.tools:
                    return [{"name": t.name, "description": t.description} for t in result.tools]
                return []
        except Exception as e:
            print(f"Failed to list tools: {e}")
            return None


def run_async(coro):
    """Helper to run async code from sync context"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=REQUEST_TIMEOUT)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class TransportationMCPClient:
    """
    Client for the Transportation Infrastructure MCP (port 9001).
    Provides bridge conditions, infrastructure costs from Statistics Canada.
    """
    
    def __init__(self, sse_url: str = None):
        self.sse_url = sse_url or MCP_TRANSPORTATION_URL
        self.async_client = AsyncMCPClient(self.sse_url)
    
    def is_available(self) -> bool:
        """Check if Transportation MCP is available"""
        return check_mcp_server_running(self.sse_url)
    
    def analyze_bridge_conditions(self, region: str) -> Optional[Dict]:
        """
        Call analyze_bridge_conditions tool.
        Returns condition percentages from Statistics Canada data.
        """
        try:
            return run_async(
                self.async_client.call_tool("analyze_bridge_conditions", {"region": region})
            )
        except Exception as e:
            print(f"analyze_bridge_conditions failed: {e}")
            return None
    
    def get_infrastructure_costs(self, infrastructure_type: str = "bridge", location: str = None) -> Optional[Dict]:
        """
        Call get_infrastructure_costs tool.
        Returns replacement costs by condition from Statistics Canada.
        """
        try:
            params = {"infrastructure_type": infrastructure_type}
            if location:
                params["location"] = location
            return run_async(
                self.async_client.call_tool("get_infrastructure_costs", params)
            )
        except Exception as e:
            print(f"get_infrastructure_costs failed: {e}")
            return None
    
    def query_bridges(self, province: str, limit: int = 100) -> Optional[Dict]:
        """
        Call query_bridges tool.
        Returns bridge data with StatCan condition distribution.
        """
        try:
            return run_async(
                self.async_client.call_tool("query_bridges", {"province": province, "limit": limit})
            )
        except Exception as e:
            print(f"query_bridges failed: {e}")
            return None
    
    def compare_across_regions(self, regions: List[str], infrastructure_type: str = "bridge") -> Optional[Dict]:
        """
        Call compare_across_regions tool.
        Compare infrastructure across provinces.
        """
        try:
            return run_async(
                self.async_client.call_tool("compare_across_regions", {
                    "regions": regions,
                    "infrastructure_type": infrastructure_type
                })
            )
        except Exception as e:
            print(f"compare_across_regions failed: {e}")
            return None
    
    def query_road_condition(
        self, 
        province: str = None, 
        highway: str = None,
        min_pci: float = None,
        max_pci: float = None,
        condition: str = None,
        limit: int = 100
    ) -> Optional[Dict]:
        """
        Call query_road_conditions tool (note: plural 'conditions').
        Returns road/highway condition data including:
        - PCI (Pavement Condition Index): 0-100 scale
        - DMI (Distress Manifestation Index)
        - IRI (International Roughness Index)
        - Pavement type, section info, coordinates
        
        PCI thresholds:
        - >=80: Good
        - 60-79: Fair  
        - 40-59: Poor
        - <40: Critical
        """
        try:
            params = {}
            if province:
                params["province"] = province
            if highway:
                params["highway"] = highway
            if min_pci is not None:
                params["min_pci"] = min_pci
            if max_pci is not None:
                params["max_pci"] = max_pci
            if condition:
                params["condition"] = condition
            params["limit"] = limit
            
            return run_async(
                self.async_client.call_tool("query_road_conditions", params)
            )
        except Exception as e:
            print(f"query_road_conditions failed: {e}")
            return None
    
    def list_tools(self) -> Optional[List[Dict]]:
        """List available tools"""
        try:
            return run_async(self.async_client.list_tools())
        except Exception as e:
            print(f"list_tools failed: {e}")
            return None


class DatasetMCPClient:
    """
    Client for the Dataset Discovery MCP (port 9000).
    Search across 250,000+ Canadian government datasets.
    """
    
    def __init__(self, sse_url: str = None):
        self.sse_url = sse_url or MCP_DATASET_URL
        self.async_client = AsyncMCPClient(self.sse_url)
    
    def is_available(self) -> bool:
        """Check if Dataset MCP is available"""
        return check_mcp_server_running(self.sse_url)
    
    def search_datasets(self, query: str, limit: int = 20) -> Optional[Dict]:
        """
        Call search_datasets tool.
        Search across all Canadian government datasets.
        """
        try:
            return run_async(
                self.async_client.call_tool("search_datasets", {"query": query, "limit": limit})
            )
        except Exception as e:
            print(f"search_datasets failed: {e}")
            return None
    
    def get_dataset_schema(self, dataset_id: str) -> Optional[Dict]:
        """
        Call get_dataset_schema tool.
        Get complete schema with field definitions and download URLs.
        """
        try:
            return run_async(
                self.async_client.call_tool("get_dataset_schema", {"dataset_id": dataset_id})
            )
        except Exception as e:
            print(f"get_dataset_schema failed: {e}")
            return None
    
    def browse_by_topic(self, topic: str) -> Optional[Dict]:
        """
        Call browse_by_topic tool.
        Explore datasets by subject area.
        """
        try:
            return run_async(
                self.async_client.call_tool("browse_by_topic", {"topic": topic})
            )
        except Exception as e:
            print(f"browse_by_topic failed: {e}")
            return None
    
    def list_tools(self) -> Optional[List[Dict]]:
        """List available tools"""
        try:
            return run_async(self.async_client.list_tools())
        except Exception as e:
            print(f"list_tools failed: {e}")
            return None


# Singleton instances
_transportation_client: Optional[TransportationMCPClient] = None
_dataset_client: Optional[DatasetMCPClient] = None


def get_transportation_client() -> TransportationMCPClient:
    """Get or create Transportation MCP client"""
    global _transportation_client
    if _transportation_client is None:
        _transportation_client = TransportationMCPClient()
    return _transportation_client


def get_dataset_client() -> DatasetMCPClient:
    """Get or create Dataset MCP client"""
    global _dataset_client
    if _dataset_client is None:
        _dataset_client = DatasetMCPClient()
    return _dataset_client


def check_mcp_health(base_url: str) -> bool:
    """Check if an MCP server is reachable"""
    return check_mcp_server_running(base_url)


def get_mcp_status() -> Dict[str, Any]:
    """Get status of all MCP servers with tool information"""
    transportation_available = check_mcp_health(MCP_TRANSPORTATION_URL)
    dataset_available = check_mcp_health(MCP_DATASET_URL)
    
    result = {
        "transportation": transportation_available,
        "dataset": dataset_available,
        "transportation_url": MCP_TRANSPORTATION_URL,
        "dataset_url": MCP_DATASET_URL,
    }
    
    # Try to get tool lists if servers are available
    if transportation_available:
        try:
            client = get_transportation_client()
            tools = client.list_tools()
            result["transportation_tools"] = tools or []
        except Exception:
            result["transportation_tools"] = []
    
    if dataset_available:
        try:
            client = get_dataset_client()
            tools = client.list_tools()
            result["dataset_tools"] = tools or []
        except Exception:
            result["dataset_tools"] = []
    
    return result
