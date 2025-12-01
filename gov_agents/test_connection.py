import asyncio
import httpx
from mcp.client.sse import sse_client

async def test_connection(url):
    print(f"Testing connection to {url}...")
    try:
        async with sse_client(url) as (read, write):
            print(f"Successfully connected to {url}")
            return True
    except Exception as e:
        print(f"Failed to connect to {url}: {e}")
        return False

async def main():
    urls = ["http://localhost:8001/sse", "http://localhost:8002/sse"]
    results = await asyncio.gather(*[test_connection(url) for url in urls])
    
    if all(results):
        print("\nAll MCP servers are reachable!")
    else:
        print("\nSome MCP servers are not reachable. Please check if they are running.")

if __name__ == "__main__":
    asyncio.run(main())
