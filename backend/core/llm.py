"""core.llm

OpenAI LLM singleton.

Import ``llm`` wherever the language model is needed (currently only in
the workflow service).
"""

from langchain_openai import ChatOpenAI

from core.config import settings


llm = ChatOpenAI(
    model=settings.OPENAI_MODEL,
    temperature=settings.OPENAI_TEMPERATURE,
    max_tokens=settings.OPENAI_MAX_OUTPUT_TOKENS,
)
