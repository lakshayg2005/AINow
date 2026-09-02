import asyncio
import pprint

from app.mcp.client import MCPClient
from app.mcp.registry import get_mcp_server


async def main():
    print("=" * 80)
    print("RAW GITHUB MCP search_repositories RESPONSE")
    print("=" * 80)

    client = MCPClient(get_mcp_server("github"))

    result = await client.call_tool(
        "search_repositories",
        {
            "query": "large language models stars:>100",
            "sort": "updated",
            "order": "desc",
            "page": 1,
            "perPage": 10,
            "minimal_output": True,
        },
    )

    print("\n1. RESULT TYPE")
    print(type(result))

    print("\n2. RESULT repr")
    pprint.pprint(result, width=140)

    print("\n3. RESULT __dict__")
    result_dict = getattr(result, "__dict__", None)
    pprint.pprint(result_dict, width=140)

    print("\n4. STRUCTURED CONTENT")
    structured = getattr(result, "structured_content", None)
    print(type(structured))
    pprint.pprint(structured, width=140)

    print("\n5. CONTENT")
    content = getattr(result, "content", None)
    print(type(content))
    pprint.pprint(content, width=140)

    if content:
        print("\n6. EACH CONTENT ITEM")
        for index, item in enumerate(content, start=1):
            print(f"\n--- ITEM {index} ---")
            print("TYPE:", type(item))

            print("repr:")
            pprint.pprint(item, width=140)

            print("__dict__:")
            pprint.pprint(getattr(item, "__dict__", None), width=140)

            text = getattr(item, "text", None)
            if text is not None:
                print("\nTEXT:")
                print(text)

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())