from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx2

from mcp import ClientSession
from mcp.client.streamable_http import (
    streamable_http_client,
)


@dataclass
class MCPServerConfig:
    name: str
    url: str
    headers: dict[str, str] | None = None


class MCPClient:
    """
    Generic client for remote MCP servers using Streamable HTTP.

    Authentication headers, proxies, timeouts, etc. are supplied
    through httpx2.AsyncClient.
    """

    def __init__(
        self,
        config: MCPServerConfig,
    ):
        self.config = config

    def _http_client(
        self,
    ) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(
            headers=self.config.headers or {},
            timeout=httpx2.Timeout(
                30.0,
                read=300.0,
            ),
            follow_redirects=True,
        )

    async def list_tools(self) -> list[Any]:
        """
        Connect to the MCP server and list its tools.
        """

        async with self._http_client() as http_client:

            async with streamable_http_client(
                self.config.url,
                http_client=http_client,
            ) as (
                read_stream,
                write_stream,
            ):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await session.initialize()

                    result = await session.list_tools()

                    return list(
                        result.tools
                    )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Connect to the MCP server and invoke one tool.
        """

        async with self._http_client() as http_client:

            async with streamable_http_client(
                self.config.url,
                http_client=http_client,
            ) as (
                read_stream,
                write_stream,
            ):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await session.initialize()

                    return await session.call_tool(
                        tool_name,
                        arguments=arguments or {},
                    )