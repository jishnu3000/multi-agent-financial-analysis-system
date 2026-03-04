"""
LangGraph multi-agent workflow.

Three sequential agents:
  1. researcher_agent  – fetches market data & news.
  2. analyst_agent     – computes technical indicators.
  3. team_lead_agent   – synthesises a final report via the Gemini LLM.

Public symbol:
    agent_workflow – compiled LangGraph graph, ready for ``agent_workflow.invoke(state)``.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from core.llm import llm
from models.agent_state import AgentState
from services.stock_data import fetch_fundamentals, fetch_news, fetch_stock_data
from services.technical import calculate_technical_indicators

# ==================== AGENT NODE FUNCTIONS ====================


def researcher_agent(state: AgentState) -> AgentState:
    """Collect raw market data for the requested ticker.

    Populates: ``stock_price_data``, ``fundamentals``, ``news_articles``,
    ``research_summary``.  Sets ``ticker_validation_error = True`` on an
    invalid ticker so downstream agents are skipped.
    """
    ticker = state["ticker"]
    errors = list(state.get("errors", []))

    try:
        stock_data = fetch_stock_data(ticker)
        state["stock_price_data"] = stock_data

        fundamentals = fetch_fundamentals(ticker)
        state["fundamentals"] = fundamentals

        news = fetch_news(ticker)
        state["news_articles"] = news

        current_price = stock_data.get('current_price') or 0
        price_change = stock_data.get('price_change') or 0
        price_change_pct = stock_data.get('price_change_pct') or 0
        low_52w = stock_data.get('low_52w') or 0
        high_52w = stock_data.get('high_52w') or 0
        news_headlines = chr(10).join(
            [f"- {a['title']}" for a in (news or [])[:3]]) or 'No news available'

        state["research_summary"] = f"""
## Research Data Collected for {ticker}

**Company:** {fundamentals.get('company_name', ticker)}
**Sector:** {fundamentals.get('sector', 'N/A')} | **Industry:** {fundamentals.get('industry', 'N/A')}

**Current Price:** ${current_price:.2f}
**Price Change:** ${price_change:.2f} ({price_change_pct:.2f}%)
**52-Week Range:** ${low_52w:.2f} – ${high_52w:.2f}

**Fundamentals:**
- Market Cap: {f"${fundamentals['market_cap']:,}" if fundamentals.get('market_cap') else 'N/A'}
- P/E Ratio: {f"{fundamentals['pe_ratio']:.2f}" if fundamentals.get('pe_ratio') else 'N/A'}
- Beta: {f"{fundamentals['beta']:.2f}" if fundamentals.get('beta') else 'N/A'}

**Recent News Headlines:**
{news_headlines}
""".strip()

        state["messages"].append(
            AIMessage(content=f"Research completed for {ticker}"))

    except ValueError as e:
        errors.append(str(e))
        state["errors"] = errors
        state["ticker_validation_error"] = True
        state["messages"].append(AIMessage(content=str(e)))
    except Exception as e:
        errors.append(f"Researcher Agent Error: {e}")
        state["errors"] = errors
        state["messages"].append(
            AIMessage(content=f"Researcher Agent Error: {e}"))

    return state


def analyst_agent(state: AgentState) -> AgentState:
    """Derive technical indicators from the collected price data.

    Populates: ``technical_analysis``, ``analyst_summary``.
    No-op when ``ticker_validation_error`` is set.
    """
    if state.get("ticker_validation_error"):
        return state

    errors = list(state.get("errors", []))

    try:
        if not state.get("stock_price_data"):
            raise ValueError("No stock price data available for analysis")

        technical = calculate_technical_indicators(state["stock_price_data"])
        state["technical_analysis"] = technical

        sma = f"${technical['sma_50']:.2f}" if technical["sma_50"] else "Insufficient data"
        rsi = f"{technical['rsi_14']:.2f}" if technical["rsi_14"] else "Insufficient data"

        state["analyst_summary"] = f"""
## Technical Analysis

**Trend Analysis:**
- 50-Day SMA: {sma}
- Current Trend: {technical['trend']} (Strength: {technical['trend_strength']:.2f}%)

**Momentum Indicators:**
- RSI (14): {rsi} – {technical['rsi_signal']}

**Support / Resistance:**
- Support Level: ${technical['support_level']:.2f}
- Resistance Level: ${technical['resistance_level']:.2f}
""".strip()

        state["messages"].append(
            AIMessage(content="Technical analysis completed"))

    except Exception as e:
        errors.append(f"Analyst Agent Error: {e}")
        state["errors"] = errors
        state["messages"].append(
            AIMessage(content=f"Analyst Agent Error: {e}"))

    return state


def team_lead_agent(state: AgentState) -> AgentState:
    """Synthesise all collected data into a final markdown report via Gemini.

    Populates: ``final_report``.
    Generates a plain-text fallback report on LLM failure.
    No-op when ``ticker_validation_error`` is set.
    """
    if state.get("ticker_validation_error"):
        return state

    ticker = state["ticker"]
    errors = list(state.get("errors", []))
    news = state.get("news_articles") or []
    research_summary = state.get(
        "research_summary") or "No research data available"
    analyst_summary = state.get(
        "analyst_summary") or "No technical analysis available"

    try:
        prompt = f"""You are a senior financial analyst creating a comprehensive stock analysis report.

Based on the following data, create a professional, well-structured markdown report for {ticker}:

{research_summary}

{analyst_summary}

News Articles:
{chr(10).join([f"- {a['title']}: {a['snippet']}" for a in news[:5]])}

Create a report with these sections:
1. Executive Summary
2. Company Overview
3. Price Performance & Fundamentals
4. Technical Analysis
5. Recent News & Market Sentiment
6. Risk Factors
7. Conclusion

Be objective, data-driven, and professional. Use the actual numbers provided."""

        response = llm.invoke(
            [
                SystemMessage(content="You are an expert financial analyst."),
                HumanMessage(content=prompt),
            ]
        )
        state["final_report"] = response.content
        state["messages"].append(AIMessage(content="Final report generated"))

    except Exception as e:
        errors.append(f"Team Lead Agent Error: {e}")
        state["errors"] = errors
        state["final_report"] = (
            f"# Stock Analysis Report: {ticker}\n\n"
            f"## Error Notice\nAn error occurred: {e}\n\n"
            f"## Available Data\n"
            f"{state.get('research_summary') or 'N/A'}\n"
            f"{state.get('analyst_summary') or 'N/A'}"
        )
        state["messages"].append(
            AIMessage(content="Fallback report generated"))

    return state


# ==================== COMPILED WORKFLOW ====================


def _build_workflow():
    """Build and compile the linear researcher → analyst → team_lead graph."""
    workflow = StateGraph(AgentState)
    workflow.add_node("researcher", researcher_agent)
    workflow.add_node("analyst", analyst_agent)
    workflow.add_node("team_lead", team_lead_agent)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "analyst")
    workflow.add_edge("analyst", "team_lead")
    workflow.add_edge("team_lead", END)

    return workflow.compile()


# Module-level singleton – imported by the analysis router
agent_workflow = _build_workflow()
