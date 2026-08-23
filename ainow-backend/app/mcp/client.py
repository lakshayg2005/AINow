from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ExternalMCPClient:

    async def fetch_url(self, url: str) -> Any:
        server_params = StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-fetch",
            ],
        )

        async with stdio_client(server_params) as (
            read,
            write,
        ):
            async with ClientSession(
                read,
                write,
            ) as session:

                await session.initialize()

                tools = await session.list_tools()

                fetch_tool = None

                for tool in tools.tools:
                    if tool.name == "fetch":
                        fetch_tool = tool
                        break

                if fetch_tool is None:
                    raise RuntimeError(
                        "Fetch MCP server does not expose a 'fetch' tool"
                    )

                result = await session.call_tool(
                    "fetch",
                    {
                        "url": url,
                    },
                )

                return result