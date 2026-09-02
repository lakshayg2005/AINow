import asyncio

from app.mcp.client import MCPClient
from app.mcp.registry import get_mcp_server


async def run_server(server_name: str):
    print("=" * 60)
    print(f"MCP SERVER: {server_name}")
    print("=" * 60)

    config = get_mcp_server(server_name)

    print(f"Name: {config.name}")
    print(f"URL:  {config.url}")

    client = MCPClient(config)

    try:
        tools = await client.list_tools()

        print(f"\nDiscovered {len(tools)} tools:\n")

        for tool in tools:
            print(f"Tool: {tool.name}")
            print(f"Title: {getattr(tool, 'title', None)}")
            print(f"Description: {getattr(tool, 'description', None)}")
            print("Input schema:")
            print(tool.input_schema)
            print("-" * 60)

    except Exception as exc:
        print(f"MCP connection failed: {exc!r}")


async def main():
    await run_server("github")
    await run_server("huggingface")


if __name__ == "__main__":
    asyncio.run(main())