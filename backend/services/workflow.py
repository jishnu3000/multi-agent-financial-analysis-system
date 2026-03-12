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
        prev_close = stock_data.get('previous_close') or 0
        price_change = stock_data.get('price_change') or 0
        price_change_pct = stock_data.get('price_change_pct') or 0
        low_52w = stock_data.get('low_52w') or 0
        high_52w = stock_data.get('high_52w') or 0
        volume = stock_data.get('volume') or 0

        mkt_cap = fundamentals.get('market_cap')
        pe = fundamentals.get('pe_ratio')
        fwd_pe = fundamentals.get('forward_pe')
        pb = fundamentals.get('price_to_book')
        div_yield = fundamentals.get('dividend_yield')
        beta = fundamentals.get('beta')
        avg_vol = fundamentals.get('avg_volume')
        description = fundamentals.get('description', '')

        def _f(v, fmt='.2f', prefix='', suffix=''):
            return f"{prefix}{v:{fmt}}{suffix}" if v is not None else 'N/A'

        mkt_cap_str = (
            f"${mkt_cap / 1e9:.2f}B" if mkt_cap and mkt_cap >= 1e9
            else f"${mkt_cap / 1e6:.2f}M" if mkt_cap and mkt_cap >= 1e6
            else _f(mkt_cap, ',.0f', '$')
        )
        div_str = f"{div_yield * 100:.2f}%" if div_yield else 'N/A'
        vol_str = f"{volume:,}" if volume else 'N/A'
        avg_vol_str = f"{avg_vol:,}" if avg_vol else 'N/A'
        sign = '+' if price_change >= 0 else ''

        news_with_snippets = chr(10).join(
            [f"- {a['title']}: {a.get('snippet', '')}" for a in (news or [])[:5]]
        ) or 'No news available'

        state["research_summary"] = f"""
## Research Data for {ticker} — {fundamentals.get('company_name', ticker)}

**Sector:** {fundamentals.get('sector', 'N/A')} | **Industry:** {fundamentals.get('industry', 'N/A')}

**Business Description:** {description or 'N/A'}

### Price Data
- Current Price:    ${current_price:.2f}
- Previous Close:   ${prev_close:.2f}
- Price Change:     {sign}${price_change:.2f} ({sign}{price_change_pct:.2f}%)
- 52-Week High:     ${high_52w:.2f}
- 52-Week Low:      ${low_52w:.2f}
- Today's Volume:   {vol_str}
- Average Volume:   {avg_vol_str}

### Fundamental Metrics
- Market Cap:       {mkt_cap_str}
- Trailing P/E:     {_f(pe)}
- Forward P/E:      {_f(fwd_pe)}
- Price/Book:       {_f(pb)}
- Dividend Yield:   {div_str}
- Beta:             {_f(beta)}

### Recent News
{news_with_snippets}
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

        sma = f"${technical['sma_50']:.2f}" if technical['sma_50'] else 'Insufficient data'
        rsi = f"{technical['rsi_14']:.2f}" if technical['rsi_14'] else 'Insufficient data'
        price = state['stock_price_data'].get('current_price', 0)

        vs_sma = ''
        if technical['sma_50'] and price:
            diff = ((price / technical['sma_50']) - 1) * 100
            sign = '+' if diff >= 0 else ''
            vs_sma = f" (price is {sign}{diff:.2f}% vs SMA)"

        state["analyst_summary"] = f"""
## Technical Analysis for {state['ticker']}

### Trend
- 50-Day SMA:        {sma}{vs_sma}
- Trend Direction:   {technical['trend']}
- Trend Strength:    {technical['trend_strength']:.2f}%

### Momentum
- RSI (14):          {rsi}
- RSI Signal:        {technical['rsi_signal']}

### Key Levels
- Support Level:     ${technical['support_level']:.2f}
- Resistance Level:  ${technical['resistance_level']:.2f}
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
        # Build an explicit flat data block so the LLM cannot claim data is missing
        stock_data = state.get('stock_price_data') or {}
        fundamentals_data = state.get('fundamentals') or {}
        technical_data = state.get('technical_analysis') or {}

        price = stock_data.get('current_price')
        prev_close = stock_data.get('previous_close')
        chg = stock_data.get('price_change', 0) or 0
        chg_pct = stock_data.get('price_change_pct', 0) or 0
        high_52w = stock_data.get('high_52w')
        low_52w = stock_data.get('low_52w')
        volume = stock_data.get('volume')
        mkt_cap = fundamentals_data.get('market_cap')
        pe = fundamentals_data.get('pe_ratio')
        fwd_pe = fundamentals_data.get('forward_pe')
        pb = fundamentals_data.get('price_to_book')
        div_yield = fundamentals_data.get('dividend_yield')
        beta_val = fundamentals_data.get('beta')
        avg_vol = fundamentals_data.get('avg_volume')
        sma50 = technical_data.get('sma_50')
        rsi14 = technical_data.get('rsi_14')
        trend = technical_data.get('trend', 'N/A')
        t_str = technical_data.get('trend_strength', 0)
        rsi_sig = technical_data.get('rsi_signal', 'N/A')
        support = technical_data.get('support_level')
        resistance = technical_data.get('resistance_level')

        def fv(v, fmt='.2f', pre='', suf=''):
            return f"{pre}{v:{fmt}}{suf}" if v is not None else 'N/A'

        mkt_cap_str = (
            f"${mkt_cap / 1e9:.2f}B" if mkt_cap and mkt_cap >= 1e9
            else f"${mkt_cap / 1e6:.2f}M" if mkt_cap and mkt_cap >= 1e6
            else fv(mkt_cap, ',.0f', '$')
        )
        sign = '+' if chg >= 0 else ''

        data_block = f"""
=== VERIFIED MARKET DATA FOR {ticker} ===
Company:          {fundamentals_data.get('company_name', ticker)}
Sector:           {fundamentals_data.get('sector', 'N/A')}
Industry:         {fundamentals_data.get('industry', 'N/A')}

--- Price ---
Current Price:    {fv(price, '.2f', '$')}
Previous Close:   {fv(prev_close, '.2f', '$')}
Price Change:     {sign}{fv(chg, '.2f', '$')} ({sign}{fv(chg_pct, '.2f', suf='%')})
52-Week High:     {fv(high_52w, '.2f', '$')}
52-Week Low:      {fv(low_52w, '.2f', '$')}
Volume:           {f"{int(volume):,}" if volume else 'N/A'}
Avg Volume:       {f"{int(avg_vol):,}" if avg_vol else 'N/A'}

--- Fundamentals ---
Market Cap:       {mkt_cap_str}
Trailing P/E:     {fv(pe)}
Forward P/E:      {fv(fwd_pe)}
Price/Book:       {fv(pb)}
Dividend Yield:   {f"{div_yield*100:.2f}%" if div_yield else 'N/A'}
Beta:             {fv(beta_val)}

--- Technical ---
50-Day SMA:       {fv(sma50, '.2f', '$')}
RSI (14):         {fv(rsi14)} — {rsi_sig}
Trend:            {trend} ({fv(t_str)}% strength)
Support:          {fv(support, '.2f', '$')}
Resistance:       {fv(resistance, '.2f', '$')}

--- Recent News ---
{chr(10).join([f"  • {a['title']}: {a.get('snippet', '')}" for a in news[:5]]) or 'No news available'}
========================================
""".strip()

        prompt = f"""You are a senior financial analyst. Write a comprehensive, professional stock analysis report for {ticker}.

ALL of the data below has been verified and collected. You MUST reference these exact numbers throughout your report — do NOT say data is unavailable or missing.

{data_block}

Additional context:
{research_summary}

{analyst_summary}

Write a report with these exact sections (use ## for headings):
1. Executive Summary
2. Company Overview
3. Price Performance & Fundamentals
4. Technical Analysis
5. Recent News & Market Sentiment
6. Risk Factors
7. Conclusion

Rules:
- Every section MUST include the specific numbers from the data block above.
- Section 3 must state the current price, 52-week range, volume, P/E, market cap, and other fundamentals explicitly.
- Section 4 must state the RSI value, SMA-50 value, trend direction, support and resistance levels explicitly.
- Section 5 must reference the actual news headlines provided.
- Do NOT write placeholder text or say any data is missing — it is all provided above.
- Be concise, factual, and data-driven."""

        response = llm.invoke(
            [
                SystemMessage(content="You are an expert financial analyst."),
                HumanMessage(content=prompt),
            ]
        )
        state["final_report"] = response.content
        state["messages"].append(AIMessage(content="Final report generated"))

    except Exception as e:
        error_str = str(e)

        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            friendly_error = (
                "**AI Service Temporarily Unavailable:** The free-tier AI quota has been "
                "exhausted due to high usage. Please wait approximately 1 minute and try again."
            )
        else:
            friendly_error = f"An unexpected error occurred while generating the report: {error_str}"

        errors.append(friendly_error)
        state["errors"] = errors
        state["final_report"] = (
            f"# Stock Analysis Report: {ticker}\n\n"
            f"## Report Generation Paused\n\n"
            f"{friendly_error}\n\n"
            f"---\n\n"
            f"## Raw Data (Retrieved Successfully)\n\n"
            f"*The following data was collected before the error occurred:*\n\n"
            f"{state.get('research_summary') or 'N/A'}\n\n"
            f"{state.get('analyst_summary') or 'N/A'}"
        )
        state["messages"].append(
            AIMessage(content="Fallback report generated due to LLM error"))

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
