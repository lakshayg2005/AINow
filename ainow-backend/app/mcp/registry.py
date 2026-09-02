from __future__ import annotations

import os

from dotenv import load_dotenv

from app.mcp.client import MCPServerConfig


load_dotenv()


def _github_headers() -> dict[str, str]:
    headers = {
        "X-MCP-Toolsets": (
            "repos,issues,pull_requests,users"
        ),
        "X-MCP-Readonly": "true",
    }

    github_token = os.getenv(
        "GITHUB_TOKEN"
    )

    if github_token:
        headers["Authorization"] = (
            f"Bearer {github_token}"
        )

    return headers


MCP_SERVERS = {
    "huggingface": MCPServerConfig(
        name="Hugging Face",
        url="https://huggingface.co/mcp",
    ),
    "github": MCPServerConfig(
        name="GitHub",
        url="https://api.githubcopilot.com/mcp/",
        headers=_github_headers(),
    ),
}


def get_mcp_server(
    name: str,
) -> MCPServerConfig:

    config = MCP_SERVERS.get(
        name
    )

    if config is None:
        raise ValueError(
            f"Unknown MCP server: {name}"
        )

    return config