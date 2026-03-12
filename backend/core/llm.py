"""
HuggingFace LLM singleton.

Import ``llm`` wherever the language model is needed (currently only in
the workflow service).
"""

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from core.config import settings

_endpoint = HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    huggingfacehub_api_token=settings.HF_API_KEY,
    task="conversational",
    temperature=0.3,
    max_new_tokens=8192,
)

# ChatHuggingFace wraps the endpoint so that:
#   • the correct "conversational" task is used (avoids the novita 400 error)
#   • .invoke([SystemMessage, HumanMessage]) returns an AIMessage with .content
llm = ChatHuggingFace(llm=_endpoint)
