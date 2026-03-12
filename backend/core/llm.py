"""
HuggingFace LLM singleton.

Import ``llm`` wherever the language model is needed (currently only in
the workflow service).
"""

from langchain_huggingface import HuggingFaceEndpoint
from core.config import settings

llm = HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    huggingfacehub_api_token=settings.HF_API_KEY,
    temperature=0.3,
    max_new_tokens=8192,
)
