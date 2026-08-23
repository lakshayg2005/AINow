import asyncio

from langchain_core.messages import HumanMessage

from app.core.llm import get_editor_llm


async def main():

    llm = get_editor_llm()

    response = await llm.ainvoke(
        [
            HumanMessage(
                content=(
                    "/no_think\n"
                    "Return exactly this JSON:\n"
                    '{"selected": [1, 2, 3]}'
                )
            )
        ]
    )

    print(
        "RAW RESPONSE:"
    )

    print(
        repr(response.content)
    )


asyncio.run(main())