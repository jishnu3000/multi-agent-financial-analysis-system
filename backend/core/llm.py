"""
Gemini LLM singleton.

Import ``llm`` wherever the language model is needed (currently only in
the workflow service).
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from core.config import settings

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.3,
    max_output_tokens=8192,
)
