"""
TypedDict definition for the shared LangGraph agent state.
Kept in its own module so all agents and routers can import it
without circular dependencies.
"""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared mutable state threaded through every LangGraph node.

    Attributes:
        ticker:                  Upper-case stock ticker symbol (e.g. ``'AAPL'``).
        messages:                Running log of LangChain message objects.

        stock_price_data:        Raw OHLCV history + metrics (Researcher).
        fundamentals:            Key financial ratios + metadata (Researcher).
        news_articles:           Recent news snippets from DuckDuckGo (Researcher).
        research_summary:        Markdown summary from the Researcher Agent.

        technical_analysis:      Computed indicators dict (Analyst Agent).
        analyst_summary:         Markdown summary from the Analyst Agent.

        final_report:            Full markdown report from the Team Lead Agent.

        errors:                  Accumulated error messages (non-fatal).
        ticker_validation_error: ``True`` when the ticker is invalid; halts
                                 downstream agents.
    """

    ticker: str
    messages: List[Any]

    # Researcher outputs
    stock_price_data: Optional[Dict[str, Any]]
    fundamentals: Optional[Dict[str, Any]]
    news_articles: Optional[List[Dict[str, str]]]
    research_summary: Optional[str]

    # Analyst outputs
    technical_analysis: Optional[Dict[str, Any]]
    analyst_summary: Optional[str]

    # Team Lead outputs
    final_report: Optional[str]

    # Error handling
    errors: List[str]
    ticker_validation_error: Optional[bool]
