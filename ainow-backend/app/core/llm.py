# from langchain_huggingface import (
#     ChatHuggingFace,
#     HuggingFaceEndpoint,
# )

# from app.core.config import settings


# def get_editor_llm():

#     endpoint = HuggingFaceEndpoint(
#         repo_id=settings.hf_model_id,
#         task="text-generation",
#         huggingfacehub_api_token=settings.hf_token,
#         provider="auto",
#         max_new_tokens=3200,
#         temperature=0.1,
#     )

#     return ChatHuggingFace(
#         llm=endpoint
#     )

#Above Code with Retry Logic
import asyncio

from langchain_huggingface import (
    ChatHuggingFace,
    HuggingFaceEndpoint,
)

from app.core.config import settings


def get_editor_llm():

    endpoint = HuggingFaceEndpoint(
        repo_id=settings.hf_model_id,
        task="text-generation",
        huggingfacehub_api_token=settings.hf_token,
        provider="auto",
        max_new_tokens=3200,
        temperature=0.1,
    )

    return ChatHuggingFace(
        llm=endpoint
    )


async def invoke_editor_llm(
    messages,
    max_retries: int = 3,
):
    llm = get_editor_llm()

    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):

        try:

            print(
                f"[LLM] Request attempt "
                f"{attempt}/{max_retries}"
            )

            return await llm.ainvoke(
                messages
            )

        except Exception as error:

            last_error = error

            print(
                f"[LLM] Attempt {attempt} failed: "
                f"{type(error).__name__}: {error}"
            )

            if attempt < max_retries:

                delay = 2 ** (
                    attempt - 1
                )

                print(
                    f"[LLM] Retrying in {delay}s..."
                )

                await asyncio.sleep(
                    delay
                )

    raise RuntimeError(
        "Hugging Face LLM failed after "
        f"{max_retries} attempts"
    ) from last_error
